import csv
import json
import subprocess
import tempfile
import argparse
import sys
import re


EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def run_cmd(cmd, allow_error=False):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and not allow_error:
        print("ERROR: 명령 실행 실패")
        print("Command:", " ".join(cmd))
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
        sys.exit(1)
    return result


def datasphere_cmd(args, host, secrets, allow_error=False):
    cmd = ["datasphere"] + args + ["--host", host, "--secrets-file", secrets]
    return run_cmd(cmd, allow_error=allow_error)


def load_json_output(result):
    txt = (result.stdout or "").strip()
    if not txt:
        return None
    try:
        return json.loads(txt)
    except Exception:
        return None


def list_users(host, secrets):
    result = datasphere_cmd(
        ["users", "list", "--accept", "application/vnd.sap.datasphere.space.users.details+json"],
        host,
        secrets,
        allow_error=True
    )
    if result.returncode != 0:
        return []
    data = load_json_output(result)
    return data if isinstance(data, list) else []


def build_user_indexes(host, secrets):
    users = list_users(host, secrets)
    by_id = {}
    by_email = {}

    for item in users:
        if not isinstance(item, dict):
            continue

        uid = (item.get("id") or "").strip().upper()
        email = (item.get("email") or "").strip().lower()

        if uid:
            by_id[uid] = item
        if email:
            by_email[email] = item

    return by_id, by_email


def exists_space(space, host, secrets):
    result = datasphere_cmd(["spaces", "read", "--space", space], host, secrets, allow_error=True)
    return result.returncode == 0


def exists_role(role, host, secrets):
    result = datasphere_cmd(["scoped-roles", "read", "--role", role], host, secrets, allow_error=True)
    return result.returncode == 0


def get_role_template_name(base_role, host, secrets):
    result = datasphere_cmd(["scoped-roles", "read", "--role", base_role], host, secrets, allow_error=True)
    if result.returncode != 0:
        print(f"ERROR: base scoped role '{base_role}' 를 읽을 수 없습니다.")
        sys.exit(1)

    data = load_json_output(result)
    if not isinstance(data, dict):
        print(f"ERROR: base scoped role '{base_role}' 의 JSON 응답을 해석할 수 없습니다.")
        sys.exit(1)

    inheritance = data.get("inheritance")
    if not inheritance:
        print(f"ERROR: base scoped role '{base_role}' 응답에서 inheritance 값을 찾지 못했습니다.")
        sys.exit(1)

    return inheritance


def create_space(space, host, secrets):
    payload = {
        space: {
            "spaceDefinition": {
                "version": "1.0.4",
                "label": space
            }
        }
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    datasphere_cmd(["spaces", "create", "--file-path", path], host, secrets)


def create_user(row, host, secrets):
    payload = [{
        "id": row["user"].upper(),
        "firstName": row.get("first_name", ""),
        "lastName": row.get("last_name", ""),
        "email": (row.get("email") or "").strip()
    }]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    datasphere_cmd(["users", "create", "--file-path", path], host, secrets)


def create_scoped_role(role, template_name, host, secrets):
    payload = {
        "name": role,
        "description": f"Generated role {role}",
        "inheritance": template_name
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name
    datasphere_cmd(["scoped-roles", "create", "--file-path", path], host, secrets)


def add_scope(role, space, host, secrets):
    result = datasphere_cmd(
        ["scoped-roles", "scopes", "read", "--role", role],
        host,
        secrets,
        allow_error=True
    )

    if result.returncode == 0:
        data = load_json_output(result)
        existing = set()

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    sid = item.get("id") or item.get("spaceId") or item.get("name")
                    if sid:
                        existing.add(sid)
                elif isinstance(item, str):
                    existing.add(item)

        if space in existing:
            return

    datasphere_cmd(
        ["scoped-roles", "scopes", "add", "--role", role, "--scopes", space],
        host,
        secrets
    )


def assign_user(space, user, role, host, secrets):
    result = datasphere_cmd(
        ["spaces", "users", "read", "--space", space, "--accept", "application/vnd.sap.datasphere.space.users.details+json"],
        host,
        secrets,
        allow_error=True
    )

    if result.returncode == 0:
        data = load_json_output(result)
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and (item.get("id") or "").upper() == user.upper():
                    roles = item.get("roles") or []
                    if role in roles:
                        return

    payload = [{"id": user.upper(), "roles": [role]}]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(payload, f)
        path = f.name

    datasphere_cmd(
        ["spaces", "users", "add", "--space", space, "--file-path", path],
        host,
        secrets
    )


def is_valid_email_format(email):
    return bool(EMAIL_PATTERN.match(email))


def normalize_row(row):
    return {
        "space": (row.get("space") or "").strip(),
        "user": (row.get("user") or "").strip().upper(),
        "scoped_role": (row.get("scoped_role") or "").strip(),
        "email": (row.get("email") or "").strip(),
        "first_name": (row.get("first_name") or "").strip(),
        "last_name": (row.get("last_name") or "").strip(),
    }


def validate_csv_rows(rows, users_by_id, users_by_email):
    errors = []
    resolved_rows = []

    for idx, raw in enumerate(rows, start=2):
        row = normalize_row(raw)
        row_errors = []

        for key in ["space", "user", "scoped_role"]:
            if not row[key]:
                row_errors.append(f"필수 컬럼 값이 비어 있습니다: {key}")

        if not row["first_name"]:
            row_errors.append("first_name 정보가 없습니다.")

        if not row["last_name"]:
            row_errors.append("last_name 정보가 없습니다.")

        if not row["email"]:
            row_errors.append("email 정보가 없습니다.")
        elif not is_valid_email_format(row["email"]):
            row_errors.append(f"이메일 형식이 올바르지 않습니다: {row['email']}")

        existing_by_id = users_by_id.get(row["user"])
        existing_by_email = users_by_email.get(row["email"].lower()) if row["email"] else None

        effective_user = row["user"]

        if existing_by_id and existing_by_email:
            id_user = (existing_by_id.get("id") or "").upper()
            email_user = (existing_by_email.get("id") or "").upper()

            if id_user != email_user:
                row_errors.append(
                    f"user와 email이 서로 다른 기존 유저를 가리킵니다. user={id_user}, email_user={email_user}"
                )
            else:
                effective_user = id_user

        elif existing_by_id and not existing_by_email:
            existing_email = (existing_by_id.get("email") or "").strip().lower()
            csv_email = row["email"].lower()
            if existing_email and existing_email != csv_email:
                row_errors.append(
                    f"user는 기존 유저와 일치하지만 email이 해당 유저의 기존 이메일과 다릅니다. existing={existing_email}, csv={csv_email}"
                )
            effective_user = (existing_by_id.get("id") or "").upper()

        elif not existing_by_id and existing_by_email:
            email_user = (existing_by_email.get("id") or "").upper()
            row_errors.append(
                f"email은 기존 유저 {email_user} 에 연결되어 있으나 CSV의 user({row['user']}) 와 일치하지 않습니다."
            )

        if row_errors:
            errors.append({
                "row_number": idx,
                "space": row["space"],
                "user": row["user"],
                "scoped_role": row["scoped_role"],
                "email": row["email"],
                "errors": row_errors
            })
        else:
            row["effective_user"] = effective_user
            row["action"] = "use_existing" if existing_by_id else "create_new"
            resolved_rows.append(row)

    return errors, resolved_rows


def print_validation_errors(errors):
    print("CSV validation failed.")
    print("다음 레코드에서 오류가 발견되었습니다:\n")
    for err in errors:
        print(
            f"[Row {err['row_number']}] space={err['space']} user={err['user']} "
            f"scoped_role={err['scoped_role']} email={err['email']}"
        )
        for msg in err["errors"]:
            print(f"  - {msg}")
        print("")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--secrets-file", required=True)
    parser.add_argument("--assignments-file", required=True)
    parser.add_argument("--default-base-role", required=True)
    args = parser.parse_args()

    template_name = get_role_template_name(args.default_base_role, args.host, args.secrets_file)
    print(f"Base role '{args.default_base_role}' -> template '{template_name}'")

    with open(args.assignments_file, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    users_by_id, users_by_email = build_user_indexes(args.host, args.secrets_file)
    errors, resolved_rows = validate_csv_rows(rows, users_by_id, users_by_email)

    if errors:
        print_validation_errors(errors)
        sys.exit(1)

    print("CSV validation passed. 작업을 시작합니다.\n")

    for row in resolved_rows:
        space = row["space"]
        csv_user = row["user"]
        role = row["scoped_role"]
        effective_user = row["effective_user"]

        print("Processing:", space, csv_user, role)

        if row["action"] == "create_new":
            print("Creating user:", csv_user)
            create_user(row, args.host, args.secrets_file)
        else:
            print(f"Using existing user: {effective_user}")

        if not exists_space(space, args.host, args.secrets_file):
            print("Creating space:", space)
            create_space(space, args.host, args.secrets_file)

        if not exists_role(role, args.host, args.secrets_file):
            print("Creating scoped role:", role)
            create_scoped_role(role, template_name, args.host, args.secrets_file)

        print("Ensuring scope:", role, "->", space)
        add_scope(role, space, args.host, args.secrets_file)

        print("Assigning user:", effective_user, "->", space, role)
        assign_user(space, effective_user, role, args.host, args.secrets_file)

        print("Done:", space, effective_user, role)
        print("------------------------------------------------")


if __name__ == "__main__":
    main()

