---
name: devops-skill
description: DevOps 基礎設施知識庫,涵蓋 AWS EKS 多叢集架構、HashiCorp Vault、ArgoCD GitOps hub-and-spoke、LiteLLM proxy、CI/CD 與 release governance(Conventional Commits/Commitizen)、PostgreSQL/RDS 管理等主題。當使用者詢問 Vault policy/遷移/升級、EKS/Karpenter/Cluster Autoscaler、ArgoCD/IRSA/OIDC、LiteLLM proxy 除錯、Bitbucket Pipelines、changelog/版本號自動化、RDS 角色權限等問題時,務必主動查閱此 skill 對應的 reference 檔案,依照既有的架構慣例與命名習慣回答,而不是從零開始給通用答案。同樣適用於面試準備、履歷撰寫、技術簡報等需要引用這些基礎設施經驗的場景。
---

# DevOps 基礎設施知識庫

這是根據過去實際處理過的 DevOps 基礎設施工作整理出來的知識庫,目的是讓後續對話能快速套用已知的架構慣例、命名習慣與踩過的坑,不用每次重新從頭解釋背景。

## 使用方式

先判斷問題落在哪個領域,再讀取對應的 reference 檔案取得詳細背景與慣例:

| 領域 | 何時查閱 | 檔案 |
|---|---|---|
| HashiCorp Vault | Vault policy 撰寫、網域遷移、版本升級、Raft snapshot、AppRole/KV v2 | `references/vault.md` |
| EKS / Kubernetes 擴縮容 | Karpenter vs Cluster Autoscaler、node group、IAM Role(cluster/node/IRSA)、HPA/KEDA、EKS 成本估算 | `references/eks-k8s.md` |
| ArgoCD / GitOps | Hub-and-spoke 架構、IRSA/OIDC 設定、rollback、CI/CD 流程分工 | `references/argocd-gitops.md` |
| LiteLLM Proxy | ALB/domain 綁定、Prometheus 監控、docker-compose 除錯、FortiGate 連線問題 | `references/litellm-proxy.md` |
| CI/CD 與 Release Governance | Bitbucket Pipelines、Conventional Commits、Commitizen、python-semantic-release、git-cliff、changelog 自動化 | `references/cicd-release.md` |
| PostgreSQL / RDS | 角色權限管理、pg_dump/restore、snapshot 流程 | `references/database-rds.md` |

## 通用原則(套用在所有領域)

- **回答語言**:預設用繁體中文回答,除非主題本身用英文更自然(例如程式碼)。
- **回答風格**:簡潔務實,直接給步驟或指令,附上真實可執行的範例(HCL、YAML、bash),避免不必要的長篇理論鋪陳。
- **命名慣例**:Vault policy/KV engine 用 `kv-{service}-{env}` 或 `kv_{service}_{env}` 的底線/連字號風格要參考既有範例模仿,不要自創新格式(細節見 `references/vault.md`)。
- **既有基礎設施背景**(每次都可以視為已知,不用使用者重複解釋):
  - 7 個 EKS 叢集,涵蓋 dev/staging/prod(含 coreapp-v2-dev/staging/prod系列)
  - Vault 目前版本 v1.21.1,AWS KMS auto-unseal + Shamir recovery seal,正在進行網域遷移
  - LiteLLM proxy 部署在 AWS EC2 後面掛 ALB
  - CI/CD:Bitbucket Pipelines 負責 build/test/push image
- **提供建議時**:優先給「和現有架構一致」的做法,而不是引入全新工具鏈,除非使用者明確想評估替代方案(例如 Karpenter vs Cluster Autoscaler 這種比較性問題才展開兩邊講)。
- **成本/資源估算類問題**:記得 Control Plane 是 per-cluster 收費($0.10/hr),7 個叢集這件事本身就是常被提出來討論「能否合併 non-prod 環境」的痛點,可主動點出。

## 何時不需要套用此 skill

單純的通用 Kubernetes/AWS/Git 知識問題(跟本環境無關,例如「什麼是 Pod」這種定義性問題)可以直接回答,不必刻意接上這裡的背景資訊,除非使用者的問題明顯是想套用在自己的架構上。
