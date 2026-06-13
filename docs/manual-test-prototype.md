# BIG 原型手工测试说明

本说明用于第一轮 CLI 原型。原型是 Python CLI，不需要传统编译；在 WSL/Linux 中推荐创建虚拟环境、安装开发依赖，然后执行 `big` 命令。

`manual-lab/` 是本地手工实验目录，已加入 `.gitignore`。实验目录可以反复生成和修改，但 `big.toml` 会记录当前系统看到的绝对路径；如果重新换路径测试，建议换一个新的 lab root 或删除旧 lab root 下的 `big.toml` 和 `.big/`。

默认设计规则：

- `/user/<username>/<flow>` 是一个工程师自己的 flow workspace。
- 未显式指定 `--branch` 时，`big commit` 不写入共享 `main`，而是写入当前 workspace 的私有 ref，例如 `workspace/default/alice/APR`。
- `big log` 不带参数时显示当前 workspace 私有 ref 的历史。
- `main` 保留给后续集成/发布流程；只有显式 `big commit --branch main ...` 才会写入 `main`。

如果你在旧原型上已经执行过 commit，那些历史可能已经写入 `main`；修正后的新 commit 不会继续默认写入 `main`。想看干净结果时，可以换一个新的 lab root，或删除当前 lab root 下的 `big.toml` 和 `.big/` 后重新初始化。

## WSL / Linux 准备

进入仓库根目录。如果仓库放在 Windows 的 `D:\Code\App\big`，在 WSL 中通常是：

```bash
cd /mnt/d/Code/App/big
```

创建并激活虚拟环境：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
make install-dev
```

验证 CLI 和自动测试：

```bash
big --help
python -m pytest
```

也可以使用 Makefile 快速验证：

```bash
make test
make smoke
```

`make smoke` 会先重置 `manual-lab/data/WslChip`，再通过 `PYTHONPATH=src python tools/run_manual_smoke.py ...` 执行一轮端到端 smoke：初始化仓库、验证 `shell-init` 输出、alice 提交、创建 `feature/place`、验证 checkout plan/copied/reused、shaqsnake 提交、验证两个用户的默认历史隔离、确认 `main` 仍为空，并检查 repo stats。它不依赖 `big` console script，但当前 Python 环境仍需要安装依赖，推荐先执行 `make install-dev`。

## WSL / Linux 手工用例

生成 WSL 专用 lab fixture：

```bash
python tools/create_manual_lab.py --root manual-lab/data/WslChip
```

该命令会生成两个用户目录，便于验证隔离行为：

```text
manual-lab/data/WslChip/user/alice/APR
manual-lab/data/WslChip/user/shaqsnake/APR
```

初始化演示仓库：

```bash
big repo init manual-lab/data/WslChip --repo-id WslChip
```

可选：初始化 3DIC 四个并行 work root：

```bash
mkdir -p manual-lab/data/StackChip_3D/user/alice/APR
mkdir -p manual-lab/data/StackChip_Top/user/alice/APR
mkdir -p manual-lab/data/StackChip_Bottom/user/alice/APR
mkdir -p manual-lab/data/StackChip_MIX/user/alice/APR

big repo init manual-lab/data/StackChip_3D \
  --repo-id StackChip \
  --integration 3d \
  --work-root 3d=manual-lab/data/StackChip_3D \
  --work-root top=manual-lab/data/StackChip_Top \
  --work-root bottom=manual-lab/data/StackChip_Bottom \
  --work-root mix=manual-lab/data/StackChip_MIX
```

期望：

- `manual-lab/data/StackChip_3D/big.toml` 是主配置，并且只有 `_3D` 下创建 `.big/`
- `_Top`、`_Bottom`、`_MIX` 下各自创建指针型 `big.toml`
- 在 `_Top/user/alice/APR` 下执行 `big status` 时，输出 `home: .../StackChip_3D`、`work_root: top .../StackChip_Top` 和 `default_ref: workspace/top/alice/APR`

进入工程师工作目录：

```bash
cd manual-lab/data/WslChip/user/alice/APR
```

查看当前 BIG 解析到的仓库和 workspace：

```bash
big status
```

期望：

- 输出 `repo: WslChip`
- 输出 `work_root: default ...`
- 输出 `workspace: user/alice/APR`
- 输出 `default_ref: workspace/default/alice/APR`
- 首次提交前 `head: -`

### 用例 1：首次提交

```bash
big commit --step place \
  --inputs 'inputs/**;scripts/**' \
  --outputs 'outputs/**;reports/**' \
  --message 'initial place snapshot'
```

期望：

- 输出 `version: v...`
- 输出 `branch: workspace/default/alice/APR`
- 输出 `inputs: 3` 和 `outputs: 2`
- `manual-lab/data/WslChip/.big/cas/objects/` 下出现 CAS 对象

检查 CAS 对象是否仍有写权限：

```bash
cd /mnt/d/Code/App/big
find manual-lab/data/WslChip/.big/cas/objects -type f -perm /222 -print
```

期望：没有输出。CAS 对象应被发布为只读文件；如果已有合法 CAS 对象曾被误改成可写，再次提交相同内容时也会被重新收紧为只读。

查看仓库存储统计：

```bash
big repo stats
```

期望：

- 输出 `versions`、`file_refs`、`logical_bytes`、`unique_referenced_bytes`、`cas_objects` 和 `cas_bytes`
- 输出 `dedupe_ratio: ...x`
- 输出按 `retention_state` 聚合的版本数和逻辑字节数，例如 `resident`

### 用例 2：查看历史和详情

```bash
big status
big log
big show <version> --full
big verify <version>
```

期望：

- `big status` 显示当前 workspace 的 `head` 等于刚才提交的 version ID
- `big log` 显示刚才的 version ID
- `big show --full` 展示 inputs、outputs、SHA-256 摘要和状态 `[Exploring/resident]`
- `big verify <version>` 输出 `integrity: ok`，表示该 version manifest 引用的 CAS 对象存在、大小一致且 SHA-256 校验通过。

### 用例 3：修改后再次提交并 diff

修改文件：

```bash
printf '\n// debug change\n' >> inputs/top.v
printf '\nCOMPONENTS 1 ;\n' >> outputs/top_placed.def
```

再次提交：

```bash
big commit --step place \
  --inputs 'inputs/**;scripts/**' \
  --outputs 'outputs/**;reports/**' \
  --message 'modified place snapshot'
```

对比两个版本：

```bash
big diff <old-version> <new-version> --verbose
```

期望：

- `recipe_hash: changed`
- diff 中出现 `~ input inputs/top.v`
- diff 中出现 `~ output outputs/top_placed.def`

### 用例 4：只移动当前 ref head 的 reset

将当前 workspace-private ref 回退到第一次提交：

```bash
big reset <old-version> --message 'rollback to initial place'
```

期望：

- 输出 `branch: workspace/default/alice/APR`
- 输出 `old_head: <new-version>`
- 输出 `new_head: <old-version>`
- 输出 `reset: moved`
- 输出 `workspace_files: unchanged`
- 工作目录里的文件不会被改回旧内容；例如刚才追加到 `inputs/top.v` 的 `// debug change` 仍然存在。

查看 reset 后的当前上下文和历史：

```bash
big status
big log
big branch events
```

期望：

- `big status` 显示 `head: <old-version>`
- `big log` 从当前 head 沿 parent 链显示历史，不再把被回退掉的 `<new-version>` 显示为当前可达历史。
- `big branch events` 显示一条 `reset` 事件，包含 `<new-version>-><old-version>` 和 `rollback to initial place`。

再次 reset 到同一个 version：

```bash
big reset <old-version>
```

期望输出 `reset: no-op`。

### 用例 5：验证两个工程师目录互相隔离

进入另一个用户的同名 flow workspace：

```bash
cd /mnt/d/Code/App/big/manual-lab/data/WslChip/user/shaqsnake/APR
```

提交同一个 step：

```bash
big commit --step place \
  --inputs 'inputs/**;scripts/**' \
  --outputs 'outputs/**;reports/**' \
  --message 'shaqsnake place snapshot'
```

查看当前目录历史：

```bash
big log
```

期望：

- 输出 `branch: workspace/default/shaqsnake/APR`
- `big log` 只显示 `shaqsnake/APR` 的历史，不混入 `alice/APR` 的提交。
- 显式执行 `big log workspace/default/alice/APR` 才会查看 `alice/APR` 的历史。
- `big log main` 默认为空，除非你显式执行过 `big commit --branch main ...`。

### 用例 6：从当前 workspace 创建命名 branch

回到 alice 的 workspace：

```bash
cd /mnt/d/Code/App/big/manual-lab/data/WslChip/user/alice/APR
```

从当前 workspace-private ref 的 head 创建命名 branch：

```bash
big branch create feature/place
```

期望：

- 输出 `branch: feature/place`
- 输出 `source_ref: workspace/default/alice/APR`
- 输出的 `head` 等于 alice 当前 workspace ref 的 head version。

查看命名 branch：

```bash
big branch list
big branch show feature/place
```

期望：

- 显示 `main`
- 显示 `feature/place`
- 不把 `workspace/default/alice/APR` 当作普通命名 branch 展示。
- `big branch show feature/place` 展示 branch kind、head version、source ref、head workspace 和 head state。

如果需要调试所有内部 ref：

```bash
big branch list --all
big branch show workspace/default/alice/APR
```

此时会额外显示 workspace-private ref。

### 用例 7：checkout 目标路径、copy-only 物化和 shell 集成

当前原型支持两步验证 checkout：先用 `--plan` 确认目标 branch、head version 和稳定目录路径；再执行不带 `--plan` 的 `big checkout <branch>`，把该 version 的 FileRef 从 CAS 复制到用户私有目标目录。CLI 子进程本身不能切换父 shell 的当前目录；未启用 shell 集成时，需要手工执行输出中的 `cd -- <target-path>`。启用 shell 集成后，wrapper 会在 checkout 成功物化或复用目录后自动进入目标目录。

```bash
big checkout feature/place --plan
```

期望：

- 输出 `branch: feature/place`
- 输出 `version: <feature/place-head-version>`
- 输出 `materialization: plan-only`
- 输出 `target_path: .../user/alice/.big-checkouts/APR/feature__place/<version>`
- 输出可复制执行的 `cd: cd -- <target-path>`
- 目标目录尚不会被创建。

执行 copy-only 物化：

```bash
big checkout feature/place
```

期望：

- 输出 `materialization: copied`
- 输出 `files: ...` 和 `bytes: ...`
- 创建目标目录 `.../user/alice/.big-checkouts/APR/feature__place/<version>`
- 在目标目录下可以看到当时 version 对应的 `inputs/`、`scripts/`、`outputs/`、`reports/` 文件
- 目标目录下存在 `.big-checkout.json` marker，用于记录 repo、branch、version、source workspace、文件数量和字节数
- 原始 workspace 不会被修改；未启用 shell 集成时，如果要进入 checkout 目录，需要手工执行输出中的 `cd -- <target-path>`

再次执行同一命令：

```bash
big checkout feature/place
```

期望输出 `materialization: reused`，表示已有 marker 匹配同一个 repo、branch 和 version，原型直接复用已有物化目录。

可选：在 Bash 或 Zsh 中启用 checkout 自动切目录：

```bash
eval "$(big shell-init bash)"
big checkout feature/place
pwd
```

期望：

- `big checkout feature/place` 仍打印原始 checkout 输出
- 如果输出不是 `materialization: plan-only`，wrapper 会读取 `cd: cd -- <target-path>` 并进入该目录
- `big checkout feature/place --plan` 只打印计划，不切目录
- 其他 `big` 命令仍透传给真实 CLI

## 当前原型范围

已实现：

- `big repo init`
- `big repo stats`
- `big status`
- `big repo init --work-root id=path` 创建 3DIC 指针型 work root 配置
- `big commit`
- `big log`
- `big show`
- `big verify`
- `big diff`
- `big reset`
- `big checkout <branch>`
- `big checkout <branch> --plan`
- `big shell-init bash|zsh`
- `big branch create`
- `big branch list`
- `big branch show`
- `big branch events`

暂未实现：

- `big restore --in-place`
- Linux groups 权限接入
- 3DIC 多 work root checkout/restore 联动
