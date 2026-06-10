# BIG 原型手工测试说明

本说明用于第一轮 CLI 原型。手工实验场位于仓库根目录下的 `manual-lab/`，该目录已加入 `.gitignore`，可以反复初始化、修改和清理。

## 准备

在仓库根目录执行：

```powershell
python -m pip install -e .
```

初始化演示仓库：

```powershell
big repo init manual-lab/data/StarterChip --repo-id StarterChip
```

进入工程师工作目录：

```powershell
Set-Location manual-lab/data/StarterChip/user/alice/APR
```

PowerShell 下建议把 glob 表达式放进同一个带引号的分号列表，避免 `**` 被 shell 提前展开成多个额外参数。

## 用例 1：首次提交

```powershell
big commit --step place `
  --inputs "inputs/**;scripts/**" `
  --outputs "outputs/**;reports/**" `
  --message "initial place snapshot"
```

期望：

- 输出 `version: v...`
- 输出 `inputs: 3` 和 `outputs: 2`
- `manual-lab/data/StarterChip/.big/cas/objects/` 下出现 CAS 对象

## 用例 2：查看历史和详情

```powershell
big log
big show <version> --full
```

期望：

- `big log` 显示刚才的 version ID
- `big show --full` 展示 inputs、outputs、SHA-256 摘要和状态 `[Exploring/resident]`

## 用例 3：修改后再次提交并 diff

修改文件：

```powershell
Add-Content inputs/top.v "wire debug_net;"
Add-Content outputs/top_placed.def "COMPONENTS 1 ;"
```

再次提交：

```powershell
big commit --step place `
  --inputs "inputs/**;scripts/**" `
  --outputs "outputs/**;reports/**" `
  --message "modified place snapshot"
```

对比两个版本：

```powershell
big diff <old-version> <new-version> --verbose
```

期望：

- `recipe_hash: changed`
- diff 中出现 `~ input inputs/top.v`
- diff 中出现 `~ output outputs/top_placed.def`

## 当前原型范围

已实现：

- `big repo init`
- `big commit`
- `big log`
- `big show`
- `big diff`

暂未实现：

- `big checkout`
- `big reset`
- `big restore --in-place`
- Linux groups 权限接入
- 3DIC 多 work root 指针配置
