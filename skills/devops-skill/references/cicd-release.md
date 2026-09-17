# CI/CD 與 Release Governance — 環境慣例

## 背景
- CI/CD 工具鏈:Bitbucket Pipelines(CI)+ ArgoCD(CD),詳見 `references/argocd-gitops.md`
- 自製工具:`generate_changelog.py`,搭配 Conventional Commits 規範讓 AI/工具能自動整理 changelog

## Conventional Commits 工具生態比較

| 工具 | 語言生態 | 自動發布 | 客製化彈性 | 備註 |
|---|---|---|---|---|
| semantic-release | Node.js | 全自動 | 高 | |
| release-please(Google) | 語言無關 | PR 審核制(開 Release PR 讓人 review 再合併發布) | 中 | 跟「手動觸發 Pipeline」的需求模式蠻契合 |
| python-semantic-release | Python | 全自動 | 高 | Python 界對標 semantic-release,適合發布到 PyPI |
| git-cliff | 語言無關 | 只管 changelog,不管版本號/tag | 極高(Tera template) | 設定檔 TOML,學習成本低,適合想要高度自訂 changelog 分類邏輯的情境 |

## python-semantic-release 使用速查

分析 commit history → 自動判斷版本號 → 產生 changelog → 打 tag,設計上就是要接進 CI **全自動跑完整流程**(含發布到 PyPI)。

```bash
pip install python-semantic-release
semantic-release version --print   # 只顯示下一版號,不執行任何動作
semantic-release version           # 正式執行:掃 commit → 判斷版號 → 更新版本檔 → 產生/更新 CHANGELOG
```

`pyproject.toml` 最小設定:
```toml
[tool.semantic_release]
version_toml = ["pyproject.toml:project.version"]
branch = "main"
changelog_file = "CHANGELOG.md"
build_command = "pip install build && python -m build"
```

## ECS 部署 Pipeline 樣板(OIDC + ECR,只給專案名稱就能套用)

這是從 `i485-blank-task` 專案實際跑過的 `bitbucket-pipelines.yml` 抽出來的樣板,涵蓋 **Bitbucket OIDC 直接認證 AWS(不用存 Access Key)→ build/push ECR → 更新 ECS Task Definition → update-service** 的完整流程,dev/staging/prod 三套環境結構一致。

### 使用方式

之後只要提供 **`{{PROJECT_NAME}}`**,其餘欄位依下面的既定慣例代入即可直接產出完整 pipeline:

| 佔位符 | 預設值/慣例 | 說明 |
|---|---|---|
| `{{PROJECT_NAME}}` | 使用者提供 | 例如 `i485-blank-task` |
| `{{ACCOUNT_ID}}` | 使用者的 AWS 帳號 ID | 固定值,向使用者確認 |
| `{{AWS_REGION}}` | `us-east-1` | 除非專案另有指定 |
| `{{ROLE_NAME}}` | `{{PROJECT_NAME}}-pipelines-role` | IAM Role 命名慣例,固定套用,role 需已透過 OIDC provider 信任 Bitbucket |
| `{{ECS_CLUSTER}}` | `default` | 除非專案另有指定 |
| `{{CONTAINER_NAME}}` | `Main` | Task Definition 裡的 container name,需與現有 Task Def 一致 |

**以下三個一定要向使用者確認、無法從專案名稱直接推導**(因為包含 AWS 產生的隨機後綴):
- Task Definition family 名稱(例如 `default-{{PROJECT_NAME}}-{{ENV}}` 或帶隨機後綴如 `default-i485-blank-task-prod-85ef`)
- ECS Service 名稱(例如 `{{PROJECT_NAME}}-{{ENV}}-85ef`)
- 各環境對應的 branch 名稱(`main` 是否等同 `prod`,或分開跑,依專案既有設定)

### 環境慣例(依範例觀察到的規則)

- **image tag 前綴規則**:
  - `main` branch(視為主要 prod 觸發來源):`IMAGE_TAG=$BITBUCKET_COMMIT`(無前綴)
  - `prod`/`staging`/`dev` branch:`IMAGE_TAG={{ENV}}-$BITBUCKET_COMMIT`(有環境前綴)
  - 同時都會額外 tag/push 一份 `{{ENV}}-latest`(main 則是純 `latest`)
- **ECR repo 路徑**:`{{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}`
- **兩個 step 為一組**:先 `Build & Push to ECR`,再 `Deploy to ECS`(讀舊 Task Def → 用 Python 替換 image → 註冊新 revision → `update-service`)

### 樣板(以單一環境為例,dev/staging/prod 三份結構相同,只換 `{{ENV}}` 相關值)

```yaml
image: atlassian/default-image:4

definitions:
  scripts:
    - &install-aws-cli >-
      curl -sSL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip &&
      unzip -q awscliv2.zip &&
      ./aws/install --update &&
      aws --version
    - &oidc-auth >-
      export AWS_REGION={{AWS_REGION}} &&
      export AWS_ROLE_ARN=arn:aws:iam::{{ACCOUNT_ID}}:role/{{ROLE_NAME}} &&
      export AWS_WEB_IDENTITY_TOKEN_FILE=$(pwd)/web-identity-token &&
      echo $BITBUCKET_STEP_OIDC_TOKEN > $(pwd)/web-identity-token &&
      aws sts get-caller-identity

pipelines:
  branches:
    {{ENV}}:   # 例如 dev / staging / prod(main 視情況套用無前綴規則)
      - step:
          name: "[{{ENV}}] Build & Push to ECR"
          oidc: true
          services:
            - docker
          script:
            - *install-aws-cli
            - *oidc-auth
            - aws ecr get-login-password --region {{AWS_REGION}} | docker login --username AWS --password-stdin {{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com
            - IMAGE_TAG={{ENV}}-$BITBUCKET_COMMIT
            - docker build -t {{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}:$IMAGE_TAG .
            - docker push {{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}:$IMAGE_TAG
            - docker tag {{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}:$IMAGE_TAG {{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}:{{ENV}}-latest
            - docker push {{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}:{{ENV}}-latest

      - step:
          name: "[{{ENV}}] Deploy to ECS"
          oidc: true
          script:
            - *install-aws-cli
            - *oidc-auth
            - IMAGE_TAG={{ENV}}-$BITBUCKET_COMMIT
            - |
              TASK_DEF=$(aws ecs describe-task-definition --task-definition {{TASK_DEF_FAMILY}} --query 'taskDefinition' --output json)
              NEW_TASK_DEF=$(echo $TASK_DEF | python3 -c "
              import json, sys
              td = json.load(sys.stdin)
              for c in td['containerDefinitions']:
                  if c['name'] == '{{CONTAINER_NAME}}':
                      c['image'] = '{{ACCOUNT_ID}}.dkr.ecr.{{AWS_REGION}}.amazonaws.com/{{ENV}}/{{PROJECT_NAME}}-{{ENV}}:$IMAGE_TAG'
              for key in ['taskDefinitionArn','revision','status','requiresAttributes','compatibilities','registeredAt','registeredBy']:
                  td.pop(key, None)
              print(json.dumps(td))
              ")
              NEW_TASK_ARN=$(aws ecs register-task-definition --cli-input-json "$NEW_TASK_DEF" --query 'taskDefinition.taskDefinitionArn' --output text)
              aws ecs update-service --cluster {{ECS_CLUSTER}} --service {{SERVICE_NAME}} --task-definition $NEW_TASK_ARN
              echo "Deploy triggered"
```

### 套用時的標準對答流程

1. 使用者只給專案名稱(例如「幫我照 ECS pipeline 樣板寫一份,專案叫 payment-api」)
2. 先確認 `{{TASK_DEF_FAMILY}}`、`{{SERVICE_NAME}}`、`{{ECS_CLUSTER}}`、`{{CONTAINER_NAME}}` 是否沿用預設慣例,或需要使用者提供實際值(這幾個常帶 AWS 隨機後綴,猜不出來)
3. 確認要產出幾套環境(通常 dev/staging/prod 三份,結構相同、只換 `{{ENV}}`)
4. 確認 IAM Role `{{PROJECT_NAME}}-pipelines-role` 是否已建立並設定好 OIDC 信任關係(如果還沒建,需要另外提醒先建立 Role,這個樣板本身不含 IAM Role 建立步驟)
5. 依上面樣板一次產出對應環境的完整 `bitbucket-pipelines.yml` 區塊

## Bitbucket Pipelines 常見踩坑

- **CHANGELOG.md 用 pipeline 自動 commit 回 repo 時的 non-fast-forward 錯誤**:根因通常是 pipeline 抓的 local branch 在它自己 commit 前就已經落後 remote 1 個以上的 commit(不是 token 權限問題,即使錯誤訊息長得很像權限錯誤)。修法是 commit 前先 `git pull`/`fetch + rebase` 同步最新 remote 狀態,再 push。
- Bitbucket Pipeline 內用 `x-token-auth` + repository access token 設定 git remote 是常見模式:
  ```bash
  git remote set-url origin https://x-token-auth:${TOKEN}@bitbucket.org/{workspace}/{repo}.git
  ```

## 時間緊迫時快速產出 CHANGELOG 的做法(沒有導入自動化工具的情境)

排序由快到慢:
1. 直接看 `git log` 整理
2. 用 AI 幫忙把 `git log` 輸出分類整理
3. 用 `gh pr list` 拉出乾淨的 PR 標題,交給 AI 分類(比純 commit message 乾淨很多)
4. 導入 `standard-version` / `release-please` 這類自動化工具(前提是已經在用 Conventional Commits 格式,否則來不及)

實務建議組合:`gh pr list` 拉 PR 標題 → AI 分類 → 人工確認 breaking changes,大概 30 分鐘內可完成一份還算像樣的 changelog。
