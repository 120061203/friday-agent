# ArgoCD / GitOps — 環境慣例

## 架構總覽:Hub-and-Spoke

- **單一 ArgoCD(hub)統管多個 EKS cluster(spoke)的 dev/staging/prod**
- 特色:Git commit 即為部署事實(deployment truth),一鍵回滾至任意版本
- 零靜態金鑰存取:IRSA + EKS Pod Identity
- 履歷/簡報用詞可參考:
  - 中文:「Hub-and-Spoke 架構,單一 ArgoCD 統管 dev/staging/prod」「一鍵回滾至任意版本,Git commit 即為部署事實」「管理 2 個 EKS 叢集 3 套環境全自動宣告式部署」
  - 英文:"One ArgoCD manages all envs" / "One-click rollback; Git commit = deployment truth" / "Zero static credentials via IRSA + Pod Identity"

## CI/CD 分工(Bitbucket Pipelines = CI,ArgoCD = CD)

```
git push
  ↓
Bitbucket Pipelines(CI)
  - build image
  - run tests
  - push image 到 ECR
  - 更新 manifest repo(image tag)
  ↓
ArgoCD(CD)
  - 偵測 manifest repo 變化
  - sync 到對應的 spoke cluster(dev/staging/prod)
```

CI(Continuous Integration):頻繁合併程式碼,自動觸發 build/test/code quality 檢查。
Continuous Delivery vs Continuous Deployment 的差異:前者自動化到「等人工核准上 prod」這一步,後者連上 prod 都全自動。目前環境是 ArgoCD 自動 sync,實務上偏向 Continuous Deployment(除非有手動 sync 的 gate)。

## IAM Role 設定(ArgoCD on EKS)

標準三顆 Role:
1. `argocd-eks-cluster-role`:`AmazonEKSClusterPolicy`,trust policy `eks.amazonaws.com`
2. `argocd-eks-node-role`:`AmazonEKSWorkerNodePolicy` + `AmazonEKS_CNI_Policy` + `AmazonEC2ContainerRegistryReadOnly`,trust policy `ec2.amazonaws.com`
   - 視需求可加 `AmazonSSMManagedInstanceCore`、`CloudWatchAgentServerPolicy`
3. Pod 層級用 IRSA pattern(不是 cluster/node role 的 trust policy 邏輯):
   - Federated OIDC principal + `sts:AssumeRoleWithWebIdentity`
   - Condition 限定 namespace + service account
   - 前提:先跑 `eksctl utils associate-iam-oidc-provider` 關聯 OIDC provider

命名慣例:`argocd-eks-cluster-role`、`argocd-eks-node-role`、`argocd-eks-argocd-role`(ArgoCD 本身用)、`argocd-eks-app-{name}-role`(各應用 Pod 用)。

## 常見追問模式

- 使用者常會直接貼現有的 IAM role 設定要求審查,回答時逐項確認是否符合最小權限原則,並在最後補一個「視需求可能還需要的 Role」表格(EBS/EFS CSI Driver、External DNS 等),不用整個重寫。
- 若問題涉及「一般 IAM Role vs IRSA 該用哪個」,參考 `references/eks-k8s.md` 的 IRSA 概念段落。
