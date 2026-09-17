---
name: devops-request
description: 引導申請者整理 DevOps 基礎設施需求，以申請說明與 Environment 表格結構產生 Jira 草稿，並在確認後建立 ticket。適用於申請或變更 ECR、ECS、Secrets Manager、RDS、LiteLLM、Lambda 等服務。
---

# DevOps 申請單

引導申請者只填實際需要的資訊，依 environment 與 service 整理成可直接審核的 Jira 草稿。除非申請者使用其他語言，預設以繁體中文對話；system name、field、enum 與 resource identifier 保留英文。

## 欄位等級

- `必填`：缺少時不得建立 ticket；只針對這類欄位提問。
- `需確認`：依上下文推導；無法推導時在完整草稿標為建議值或 `none`，不要單獨追問。
- `分配後確認`：可先建立 ticket，在對應 service table 填 `pending-after-assignment`。
- `條件`：適用時才納入；無法判斷時省略，或在會影響執行範圍時填 `none` 並簡述假設。
- `選填`：未提供時採 catalog 預設；沒有預設且不影響執行時可省略。
- `可預設`：採 catalog 明確預設；沒有明確預設時填 `DevOps standard`。

## 資料來源與安全

- 只把目前申請對話中由申請者明確提供的內容視為已確認資料。
- 只有申請者明確要求檢查或沿用指定 repository、Jira、AWS 或其他來源時，才讀取該來源。
- 套用順序為：申請者明確指定值、catalog 明確預設值、`DevOps standard`。
- `requested_by` 預設為目前申請者或 Jira reporter；缺少團隊或聯絡資料時不要追問。
- 不得推測 AWS account、ARN、resource ID、permission、current state 或 Jira metadata。
- 禁止在問題、草稿或 Jira 填入 password、token、API key、private key 或其他 credential value；只記錄 key name、secret path 與 secure reference。
- 若申請者貼出 credential，不得重述；提醒使用安全管道並輪替已暴露的 credential。同一事件只提醒一次。

## 作業流程

1. 辨識 `project_name`、`business_purpose`、`operation`、`environments`、主要 service、`requested_by` 與 `required_by`。
2. 正規化 environment heading：`development` → `dev`、`testing` → `test`、`production` → `prod`；其他 environment 保留申請者使用的名稱。
3. 依 primary service 讀取本文件對應的 catalog 段落。
4. 主動詢問連動服務：申請 ECS 或 Lambda 時，詢問是否有連動的 RDS（host、database name、table/schema、帳號類型與權限層級：`readonly` / `read-write` / `admin`）、Secrets Manager、或其他 service。有連動 service 時一併收集對應 catalog 必填欄位。
5. 只收集缺少且無法推導的 `必填` 欄位；多個缺漏一次集中提出。
6. 依「Jira description contract」產生完整草稿。只保留對執行有意義的 rows，不要把每個未使用的 catalog field 都填成 `none`。
7. 顯示 project、issue type、summary、description 與其他預計寫入欄位，等待申請者在新的訊息中明確確認。
8. 確認後才建立 Jira ticket，並讀回驗證。草稿有修改時，重新顯示完整草稿並再次取得確認。

## 缺漏必填問題

每批問題使用連續編號；一個 logical field 只占一個編號。說明格式、允許值與是否需要依 environment 提供。缺漏階段只顯示必填問題，不顯示推導值、預設值或草稿。

```text
1. <欄位名稱> (`<catalog key>`)：
   <要提供的內容、允許值或格式；需要時說明 environment mapping。>
   例如：<只有格式不直觀時提供不含真實 credential 的範例>

請依相同編號一次回覆；不知道時也請保留編號並說明。
```

## Environment 與 service 組織規則

- 草稿使用**橫向多欄 table**：每個 service 一張表，欄為 `Key | dev | staging | prod`（依實際申請的 environment 動態調整欄數）。
- Service 使用短而明確的名稱，例如 `ECS`、`Lambda`、`ECR`、`Secrets Manager`、`RDS`、`LiteLLM`。
- Environment 欄順序固定為 `dev`、`test`、`staging`、`prod`，其他 environment 接在後面。
- 同一 key 在不同 environment 的值不同時，各欄填各值；完全相同時各欄仍重複填入，不合併。
- `new` companion 要有 service table；`existing` companion 在相關 primary service table 以 resource reference 說明；`not-needed` companion 不輸出。
- 不建立獨立的 `Companion Decisions`、`Pending Confirmations` 或 `Acceptance Criteria` 章節。需要分配後確認的內容直接放進 service table，填 `pending-after-assignment`。
- Table row 的 value 要標示來源：申請者提供的值直接呈現；預設或建議值以簡短括號標記 `catalog 預設`、`DevOps standard` 或 `草稿建議`。
- 不輸出 JSON、canonical service ID、versioned spec 或與 description 重複的 machine-readable payload。

## 共用申請項目

| Key | 等級 | 說明 |
| --- | --- | --- |
| `project_name` | 必填 | Project/service 正式名稱 |
| `business_purpose` | 必填 | 使用情境、要解決的問題與預期成果 |
| `environments` | 必填 | `dev`、`test`、`staging`、`prod` 或其他 environment |
| `operation` | 必填 | `create`、`update`、`grant-access`、`migrate` 或其他明確操作 |
| `requested_by` | 選填 | 目前申請者或 Jira reporter |
| `required_by` | 必填 | `YYYY-MM-DD` 或 `no-deadline` |
| `production_impact` | 必填 | 有 `prod` 時為 `yes`；否則只有可能影響既有 production resource、traffic、data 或 permission 時才詢問 |
| `existing_resource_reference` | 條件 | 操作既有資源時提供 name、ARN、ID 或 URL |
| `change_window` | 條件 | Production cutover 或時段限制 |
| `downtime_tolerance` | 條件 | 可能中斷服務時提供；不可中斷時填 `none` |
| `repository_url` | 條件 | Application、IaC 或 deployment repository |
| `related_links` | 條件 | 相關 Jira、spec、runbook 或 architecture document |

`production_impact`、`existing_resource_reference`、`change_window`、`downtime_tolerance`、`repository_url` 與 `related_links` 不另設總覽章節；適用時放進「申請說明」的 metadata table，或放進最相關的 service table。

## Jira description contract

固定使用以下層級與順序：

```md
# 申請說明

<business_purpose；一至三個短段落>

| Key | Value |
| --- | --- |
| `project_name` | <value> |
| `operation` | <value> |
| `requested_by` | <value> |
| `required_by` | <YYYY-MM-DD 或 no-deadline> |
| `production_impact` | <yes/no；yes 時簡述影響> |
| <其他適用的共用項目> | <value> |

## ECS

| Key | dev | staging | prod |
| --- | --- | --- | --- |
| `service_names` | sample-service-dev | sample-service-staging | sample-service-prod |
| `container_port` | 8080 | 8080 | 8080 |
| `health_check_path` | /health | /health | /health |
| `region` | us-east-1 | us-east-1 | us-east-1 |
| <其他適用設定> | <dev value> | <staging value> | <prod value> |

## Secrets Manager

| Key | dev | staging | prod |
| --- | --- | --- | --- |
| `secret_paths` | /sample-service/dev | /sample-service/staging | /sample-service/prod |
| `key_names` | pending-after-assignment | pending-after-assignment | pending-after-assignment |
| <其他適用設定> | <dev value> | <staging value> | <prod value> |

## RDS

| Key | dev | staging | prod |
| --- | --- | --- | --- |
| `instance_or_host` | <dev host> | <staging host> | <prod host> |
| `database_names` | <dev db> | <staging db> | <prod db> |
| `schemas_tables` | <scope> | <scope> | <scope> |
| `permissions` | read-write | read-write | readonly |
| <其他適用設定> | <dev value> | <staging value> | <prod value> |
```

- Environment 欄只列實際申請的 environment，不申請的欄位直接省略。
- 沒有某個 service 時直接省略該 service section，不輸出空 heading 或 `none` table。

## Jira 草稿與建立

- Project 固定為 `PROJ`。優先使用 Atlassian Rovo MCP；建立前查詢 project metadata、可用 issue type、required fields 與允許值。
- 申請者已指定 issue type 時直接採用；否則優先建議 `Task`。沒有 `Task` 時採第一個 non-subtask issue type。
- Assignee 預設不指定；未提供的 priority、label、due date 與其他選填欄位不得自行補值。
- `required_by` 只寫入 description；除非申請者明確要求設定 Jira due date，否則不得把 `required_by` 自動映射到 due date。
- Summary 使用 `<project_name> - <operation> <primary services> (<environments>)`。
- 預設將同一成果的 primary 與 companion services 整理為一張 ticket；只有申請者要求，或 owner、issue type、時程或 scope 明顯獨立時才拆單。
- 建立後讀回確認 project、issue key、summary、description 與本次指定欄位，確認沒有意外變更。
- 完成後回覆 ticket key、URL、summary、留空欄位、`pending-after-assignment` 與採用的預設值。工具無法建立或讀回時不得聲稱成功。

## 建立前檢查

- 所有 `必填` 共用與 service fields 已完成。
- 每個 environment 的 primary service 都有 table；每個 `new` companion 都有 table。
- Environment、service、resource name 與 operation 沒有互相衝突。
- 只輸出適用 rows；省略不影響執行的空值。
- 所有 `pending-after-assignment` 都位於對應 service table。
- Ticket 不包含 credential value。
- Production impact、change window、downtime 與 rollback/recovery 沒有矛盾。

## 服務設定 catalog

### Amazon ECR

| Key | 等級 | 常見設定 |
| --- | --- | --- |
| `repository_names` | 必填 | 各 environment 的 repository name |
| `region` | 可預設 | 預設 `us-east-1`；需要其他 region 時明確指定 |
| `image_producers_consumers` | 必填 | Push/pull 的 pipeline、role、service |
| `tag_mutability` | 可預設 | Mutable 或 immutable tag；預設 `immutable` |
| `image_scanning` | 可預設 | Scan on push 或 enhanced scanning；預設啟用 |
| `encryption` | 可預設 | AES-256 或 KMS key |
| `lifecycle_policy` | 可預設 | Image 保留數量、untagged image expiry |
| `cross_account_access` | 條件 | Cross-account principal 與 permission |

### Amazon ECS / Fargate

| Key | 等級 | 常見設定 |
| --- | --- | --- |
| `service_names` | 必填 | 各 environment 的 ECS service name |
| `region` | 可預設 | 預設 `us-east-1`；需要其他 region 時明確指定 |
| `deployment_mode` | 可預設 | 預設 `ECS Express Mode`；需要 Fargate、EC2 launch type 或既有 cluster 時再指定 |
| `cluster_name` | 條件 | 既有或指定 cluster name |
| `ecr_repositories` | 可預設 | 預設依各 environment 的 `service_names` 建立同名 ECR repository |
| `task_cpu_memory` | 必填 | 各 environment 的 Task CPU 與 Memory，詢問時提供常用選項：`0.25 vCPU / 512 MB`、`0.5 vCPU / 1 GB`、`1 vCPU / 2 GB`、`2 vCPU / 4 GB`、`4 vCPU / 8 GB`；可自填其他合法組合 |
| `desired_count_autoscaling` | 可預設 | Desired count、min/max capacity、scaling signal |
| `container_port` | 必填 | Container listen port |
| `health_check_path` | 必填 | Health check HTTP path，例如 `/health`、`/api/health` |
| `health_check_protocol_interval` | 可預設 | Protocol、interval、timeout 使用 `DevOps standard` |
| `environment_variables` | 條件 | 非敏感 environment variable name/value |
| `secret_key_names` | 條件 | 要注入的 secret key name，禁止 secret value |
| `network_exposure` | 選填 | Internal、public、限定 VPC/service 或無 inbound traffic；預設 `public` |
| `load_balancer` | 條件 | ALB/NLB、listener、target group、routing path |
| `task_roles` | 可預設 | Task role、execution role 與必要 permission scope |
| `logging` | 可預設 | Log group、retention、structured log requirement |
| `deployment_strategy` | 可預設 | Rolling、blue/green、A/B standby |
| `rollback_plan` | 選填 | Previous image/task definition 與 rollback trigger；預設回復上一個 image/task definition |

### AWS Secrets Manager

| Key | 等級 | 常見設定 |
| --- | --- | --- |
| `operation` | 必填 | `create`、`add-keys`、`update-keys`、`grant-access` |
| `region` | 可預設 | 預設 `us-east-1`；需要其他 region 時明確指定 |
| `secret_paths` | 必填 | 各 environment 的 secret path/name；只列 path，禁止填入 value |
| `key_names` | 分配後確認 | Ticket 分配後由負責人與申請者確認；只記錄 key name，禁止 value |
| `value_delivery_reference` | 分配後確認 | 負責人與申請人確認安全交付方式，禁止 Jira 明文 |
| `consumers` | 條件 | 需要讀取的 service、role 或 user；同一申請已包含 ECS/Lambda 時直接推導，不得追問 |
| `writers` | 條件 | 需要寫入/rotation 的 role 或 process |
| `kms_key` | 可預設 | Default key 或指定 KMS key |
| `rotation_expiry` | 可預設 | Rotation schedule、expiry、handover owner |
| `replication` | 條件 | Multi-region replication requirement |

在 `key_names` 與 `value_delivery_reference` 完成確認前，不得建立或更新 secret。

### Amazon RDS / Aurora

| Key | 等級 | 常見設定 |
| --- | --- | --- |
| `engine_version` | 必填 | PostgreSQL、MySQL、Aurora 與 version |
| `instance_or_host` | 條件 | 既有 instance/cluster/host；新建時可由 DevOps 選擇 |
| `region` | 可預設 | 預設 `us-east-1`；需要其他 region 時明確指定 |
| `database_names` | 必填 | 各 environment 的 database name |
| `accounts` | 必填 | Application、migration、readonly 或 human account |
| `permissions` | 必填 | Connect、DDL、DML、readonly 等精確權限 |
| `connectivity_sources` | 必填 | ECS、Lambda、VPC、VPN、bastion 或受控 source IP |
| `schemas_tables` | 條件 | Schema、table、view、sequence scope |
| `migration_scope` | 條件 | Migration source、script、owner、執行時機 |
| `data_operation` | 條件 | Import/export/backfill 的 source、target、volume、validation |
| `availability_capacity` | 可預設 | Instance size、storage、Multi-AZ、autoscaling |
| `backup_retention` | 可預設 | Backup window、retention、restore requirement |
| `credential_key_names` | 選填 | DB credential key name；預設 `DB_HOST`、`DB_PORT`、`DB_USERNAME`、`DB_PASSWORD`，禁止填入 value |
| `rollback_recovery` | 條件 | 涉及 schema migration、data change 或 production 資料時，說明 rollback/restore 方式 |

### LiteLLM

| Key | 等級 | 常見設定 |
| --- | --- | --- |
| `team_name` | 必填 | LiteLLM team/project name |
| `models` | 必填 | 精確 model name/alias |
| `key_aliases` | 選填 | 預設依 `<project>-<environment>` 命名；只填 alias，禁止 actual key |
| `api_capabilities` | 選填 | 預設 `Chat/Responses`；需要 `Embeddings`、`Files`、`Batch` 等額外 API 時再指定 |
| `spend_limit_period` | 可預設 | 預設採用 DevOps 標準 quota 與 daily/monthly period |
| `rpm_tpm` | 可預設 | Requests/tokens per minute |
| `consumers` | 選填 | 預設為目前申請的 project/application；需要其他 consumer 時再指定 |
| `secret_destination` | 分配後確認 | 負責人與申請人確認 key 的 secret path，禁止 value |
| `usage_owner` | 分配後確認 | 負責人與申請人確認 usage、cost、model availability owner |
| `usage_alert` | 可預設 | Threshold、notification channel |

### AWS Lambda

| Key | 等級 | 常見設定 |
| --- | --- | --- |
| `function_names` | 必填 | 各 environment 的 function name |
| `region` | 可預設 | 預設 `us-east-1`；需要其他 region 時明確指定 |
| `runtime_architecture` | 必填 | Runtime version、`x86_64` 或 `arm64` |
| `handler` | 必填 | Handler/entry point |
| `triggers` | 需確認 | API Gateway、SQS、EventBridge、S3、manual 或其他 trigger；不需要時記錄 `none` |
| `memory_timeout_storage` | 可預設 | Memory、timeout、ephemeral storage |
| `concurrency` | 可預設 | Reserved/provisioned concurrency |
| `retry_failure_destination` | 可預設 | Retry、DLQ、on-failure destination |
| `vpc_connectivity` | 條件 | VPC、subnet、security group；需要 private resource 時填寫 |
| `environment_variables` | 條件 | 非敏感 environment variable |
| `secret_key_names` | 條件 | Secret key name 與來源，禁止 value |
| `execution_role` | 可預設 | Execution role 與必要 action/resource scope |
| `logging_tracing` | 可預設 | CloudWatch Logs、retention、X-Ray tracing |
| `version_alias` | 條件 | Version、alias 與 environment mapping |
| `rollback_plan` | 必填 | Previous version/alias 與 rollback trigger |
