# EKS / Kubernetes 擴縮容與架構 — 環境慣例

## 現況背景
- 7 個 EKS 叢集,涵蓋 dev/staging/prod(coreapp-v2-dev/staging/prod、Atlas 系列等)
- Region 主要用 Singapore(ap-southeast-1)、us-west-2、us-east-1 混用(依專案而定)
- 目前 node autoscaling 用的是哪一套(CA 或 Karpenter)需視當下對話脈絡確認,不要假設已導入 Karpenter

## Karpenter vs Cluster Autoscaler(常見比較問題)

| | Cluster Autoscaler | Karpenter |
|---|---|---|
| 擴展單位 | Node Group(ASG) | 直接建立 EC2 instance |
| 決策速度 | 較慢,受 ASG API 限制 | 較快,即時計算最佳 instance |
| Instance 彈性 | 需預先定義多個 ASG 對應不同機型 | NodePool/NodeClass 定義條件,自動挑選最省成本機型 |
| Bin-packing/整併 | 較弱 | 較強,會主動整併/替換節點降低成本 |

- Karpenter 關鍵資源(v1 API):`NodePool`(排程限制條件:instance family、capacity type on-demand/spot、taints)、`EC2NodeClass`(AMI、subnet、security group、IAM instance profile)
- 建議情境:管理多組 EKS cluster、想用 spot 混用降低成本、想減少手動維護多組 node group,適合評估遷移到 Karpenter
- Cluster Autoscaler 原生機制:偵測 Pending Pod → 模擬計算加節點能否排上 → 呼叫雲端 API 把對應 ASG desired capacity +1;縮容則反向判斷利用率與可安全驅逐性
  - 關鍵參數:`--scale-down-utilization-threshold`、`--scale-down-unneeded-time`

## HPA + Cluster Autoscaler/Karpenter 搭配

HPA 負責 Pod 層級擴容(「我需要更多 Pod」),Cluster Autoscaler/Karpenter 負責 Node 層級擴容(「幫你開新節點來放這些 Pod」),兩者要搭配才是完整的 auto scaling。

面試/簡報時可以這樣講(英文版本已驗證過好用):
> "HPA handles Pod-level scaling, but I'd also add Cluster Autoscaler to automatically provision new Nodes when existing ones are full — so scaling works end to end."

HPA 進階細節:
- 控制迴圈定期算 replica 數(依 Resource/Custom Prometheus Adapter/External 三種 metrics source)
- Stabilization window 分別控制 scale-up/scale-down 行為,避免抖動
- SQS-based event-driven scaling 用 KEDA(ScaledJob),不是單純 HPA 能處理的場景
- **HPA 與正在進行的 Rolling Update 有交互作用風險**:高流量部署前建議先手動調高 `minReplicas` 預先擴容,避免部署期間流量進來但擴容跟不上

## EKS IAM Role 標準配置(建立新 cluster 時的檢查清單)

1. **EKS Cluster Role**:`AmazonEKSClusterPolicy`,trust policy 為 `eks.amazonaws.com`
2. **EKS Node Role**:
   - `AmazonEKSWorkerNodePolicy`(node 加入 cluster 基本權限)
   - `AmazonEKS_CNI_Policy`(VPC CNI 管理 ENI)
   - `AmazonEC2ContainerRegistryReadOnly`(從 ECR pull image)
   - `CloudWatchAgentServerPolicy`(若有用 CloudWatch Agent/Container Insights)
   - trust policy 為 `ec2.amazonaws.com`
3. **App Pod Role(IRSA)**:依服務需求給最小權限(例如限定 Secrets Manager 路徑、S3 bucket prefix),SES 建議加 Condition 限定 `FromAddress` 避免濫用
4. **ALB Controller Role(IRSA)**:用官方 IAM policy JSON(`aws-load-balancer-controller` repo 的 `iam_policy.json`)

視需求額外考慮:
| 情境 | 需要的 Role |
|---|---|
| Cluster Autoscaler | Pod Role with `autoscaling:*`(IRSA) |
| External DNS | Pod Role with `route53:*`(IRSA) |
| EBS CSI Driver | IRSA Role with `AmazonEBSCSIDriverPolicy` |
| EFS CSI Driver | IRSA Role with `AmazonEFSCSIDriverPolicy` |

命名慣例參考:`{project}-{env}-alb-controller-role`、`argocd-eks-cluster-role`、`argocd-eks-node-role`、`argocd-eks-{app}-role`。

## IRSA 概念(常需要跟同事/面試官解釋)

一般 IAM Role 綁在 Node 上 → 同節點所有 Pod 共用同一組權限(權限範圍過大)。
IRSA(IAM Roles for Service Accounts)→ 每個 Pod 依 Service Account 拿到獨立、最小化的權限。

流程:Pod 帶著 EKS 簽發的身份證明 → AWS 透過 OIDC 驗證 → AWS 把對應 IAM Role 權限交給該 Pod → 不需要任何金鑰,Pod 重啟自動重新取得,權限到期自動換新。

前提:cluster 要先關聯 OIDC provider(`eksctl utils associate-iam-oidc-provider`),順序是 OIDC 先、IRSA 後。

Dev 環境趕時間可以先用一般 Node IAM Role 頂著,之後再補 IRSA 沒關係;正式環境(prod)應該用 IRSA。

## EKS 成本估算重點(常被問到的「這樣一個月多少錢」)

- **Control Plane**:固定 $0.10/hr per cluster,與 node 數量無關 → 7 個 cluster 光 control plane 就是 $0.10 × 7 × 720 ≈ $504/月(約台幣 $16,000/月)
- **Node**:按 EC2 定價(t3.medium/m5.large/m5.xlarge/c5.xlarge 等),Spot 通常省 ~70%
- **容易被忽略的隱藏費用**:NAT Gateway($0.045/hr + $0.045/GB 流量,private subnet 架構下所有 outbound 都走這裡)、跨 AZ data transfer($0.01/GB)
- **省錢常見做法**:
  - dev/staging 用 namespace 隔離取代獨立 cluster(prod 建議仍維持獨立 cluster 做安全隔離)
  - stateless 服務放 Spot,DB/有狀態服務放 On-Demand
  - 用 Karpenter 做 autoscaling,idle 時縮到最小
  - 同 AZ Pod 互通避免跨 AZ 流量費
  - 非 prod 環境下班時間 scale to zero
- 若使用者提到「7 個 cluster 是不是很貴」,可以主動點出這是常見的架構討論痛點(coreapp 系列本身就是 3 個獨立 cluster:dev/staging/prod)

## Zero-downtime 部署細節(Rolling Update 之外還要補的)

- Readiness Probe 設定要正確,不然流量會打到還沒準備好的 Pod
- PreStop hook + sleep delay,處理 ALB deregistration 的延遲(避免連線在 ALB 還沒完全移除節點前就被切斷)
- PodDisruptionBudget(PDB):處理 node 層級的中斷(如 node 維護、Karpenter 整併節點)
- `maxUnavailable: 0` 搭配 Rolling Update,確保任何時刻都有足夠 Pod 服務流量
