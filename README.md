
# SAP Datasphere CLI 기반 Bulk Provisioning 사용 가이드

본 문서는 SAP Datasphere CLI를 사용하여 **사용자, Space, Role을 자동으로 생성 및 할당하는 Python 스크립트**를 실행하기 위한 환경 구성 및 실행 방법을 설명합니다.
(https://www.npmjs.com/package/@sap/datasphere-cli#from-the-command-line:)

본 자동화 스크립트는 다음 작업을 수행합니다.

- CSV 기반 사용자 관리  
- Datasphere User 생성  
- Space 생성  
- Scoped Role 생성  
- User-Space Role Assignment  

---

# 1. 사전 요구사항 (Prerequisites)

다음 환경이 필요합니다.

| 항목 | 요구사항 |
|---|---|
| OS | Mac / Linux / Windows |
| Node.js | v18 이상 |
| Python | 3.9 이상 |
| SAP Datasphere | Admin 권한 |

---

# 2. SAP Datasphere CLI 설치

Datasphere CLI는 npm 패키지로 제공됩니다.

```bash
npm install -g @sap/datasphere-cli
```

또는

```bash
yarn global add @sap/datasphere-cli
```

설치 확인

```bash
datasphere -v
```

---

# 3. OAuth Client 생성

Datasphere Tenant에서 OAuth Client를 생성합니다.

경로

```
System → Administration → App Integration → OAuth Clients → +Add an OAuth Client
```

생성 시 필요한 정보

| 항목 | 설명 |
|---|---|
| Name | OAuth Client 명 (예: OAuth for CLI) |
| Purpose | Interactive Usage |
| Redirect URI | https://localhost:8080 |

생성 후에 반드시 Secret key를 별도로 저장해 놓아야 하며, 생성 화면을 벗어나게 되면 새로운 OAuth Client를 다시 생성하지 않는 한 해당 Secret key를 다시 받을 수 없습니다.

| 항목 | 설명 |
|---|---|
| Client ID | CLI 인증용 |
| Client Secret | CLI 인증용 |
| Authorization URL | Tenant 인증 URL |
| Token URL | Token 발급 URL |

---

# 4. CLI 로그인

```bash
datasphere login
```

입력 정보

- Client ID  
- Client Secret  
- Authorization URL  
- Token URL  

로그아웃

```bash
datasphere logout
```

인증정보 확인

```bash
datasphere secrets show
```

---

# 5. secrets.json 방식 인증 (권장)

자동화 스크립트에서는 secrets.json 방식 사용을 권장합니다.

예시

```json
{
 "tenantUrl": "https://mytenant.ap12.hcs.cloud.sap",
 "access_token": "<access token>"
}
```

---

# 6. CLI 초기화

Tenant service document 다운로드

```bash
datasphere config cache init   --host https://<tenant>.hcs.cloud.sap   --secrets-file secrets.json
```

---

# 7. CLI 명령 확인

전체 명령 확인

```bash
datasphere -h
```

Tenant 기준 명령 확인

```bash
datasphere -H https://<tenant>.hcs.cloud.sap -h
```

Space 명령

```bash
datasphere spaces -h
```

---

# 8. GitHub Repository 다운로드

```bash
git clone https://github.com/<repo>/datasphere-cli-bulk-provisioning.git
```

또는 GitHub에서 ZIP 다운로드

Repository 구조

```
datasphere-cli-bulk-provisioning
│
├ scripts
│  datasphere_training_env_cli_bulk.py
│
├ examples
│  datasphere_assignments_sample.csv
│
└ docs
```

---

# 9. CSV 입력 파일 구성

CSV 형식

```
space,user,scoped_role,email,first_name,last_name
TA_1,trainee01,TA_1_ADMIN,trainee01@company.com,Jisoo,Park
TA_2,YSGMAIL,TA_2_ADMIN,youngseols@gmail.com,Gmail,Young
```

| 컬럼 | 설명 |
|---|---|
| space | 생성할 Datasphere Space |
| user | Datasphere User ID |
| scoped_role | 생성할 Scoped Role |
| email | 사용자 이메일 |
| first_name | 사용자 이름 |
| last_name | 사용자 성 |

---

# 10. Python 스크립트 실행

```bash
python3 scripts/datasphere_training_env_cli_bulk.py   --host https://<tenant>.hcs.cloud.sap   --secrets-file secrets.json   --default-base-role ACADEMY_ADMIN   --assignments-file examples/datasphere_assignments_sample.csv
```

옵션 설명

| 옵션 | 설명 |
|---|---|
| --host | Datasphere Tenant URL |
| --secrets-file | 인증 정보 |
| --default-base-role | 기본 Role Template |
| --assignments-file | 입력 CSV |

---

# 11. 실행 프로세스

```
1 CSV Validation
2 Datasphere User 확인
3 User 생성 (없을 경우)
4 Space 생성
5 Scoped Role 생성
6 User → Space Role Assign
```

예시 실행 로그

```
CSV validation passed. 작업을 시작합니다.

Processing: TA_1 TRAINEE01 TA_1_ADMIN
Using existing user: TRAINEE01
Creating space: TA_1
Creating scoped role: TA_1_ADMIN
Assigning user: TRAINEE01 -> TA_1 TA_1_ADMIN
```

---

# 12. CSV Validation 로직

검증 항목

- email 형식
- first_name / last_name 존재 여부
- user / email 기존 유저 충돌 여부
- user 대소문자 자동 처리

오류 발생 시 provisioning 중단

예시

```
CSV validation failed

Row 3
 - email 형식 오류
 - user/email mismatch
```

---

# 13. 문제 해결

CLI 로그 활성화

```bash
LOG_LEVEL=6 datasphere spaces read
```

| 값 | 의미 |
|---|---|
|1|Inactive|
|2|Error|
|3|Warning|
|4|Info|
|5|Debug|
|6|Trace|

---

# 14. 보안 주의사항

다음 파일은 GitHub에 업로드하지 않습니다.

```
secrets.json
.env
access_token
```

.gitignore 예시

```
secrets.json
.env
__pycache__
*.pyc
```

---

# 15. 지원 문의

CLI 문제 발생 시

SAP Support Component

```
DS-API-CLI
```

SAP Community

```
tag: datasphere-cli
```
