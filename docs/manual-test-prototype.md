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

`make smoke` 会使用 `manual-lab/data/WslChip`，并通过 `PYTHONPATH=src python -m big ...` 执行一轮 init、commit、log。它不依赖 `big` console script，但当前 Python 环境仍需要安装依赖，推荐先执行 `make install-dev`。

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

进入工程师工作目录：

```bash
cd manual-lab/data/WslChip/user/alice/APR
```

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

### 用例 2：查看历史和详情

```bash
big log
big show <version> --full
```

期望：

- `big log` 显示刚才的 version ID
- `big show --full` 展示 inputs、outputs、SHA-256 摘要和状态 `[Exploring/resident]`

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

### 用例 4：验证两个工程师目录互相隔离

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

### 用例 5：从当前 workspace 创建命名 branch

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

## 当前原型范围

已实现：

- `big repo init`
- `big commit`
- `big log`
- `big show`
- `big diff`
- `big branch create`
- `big branch list`
- `big branch show`

暂未实现：

- `big checkout`
- `big reset`
- `big restore --in-place`
- Linux groups 权限接入
- 3DIC 多 work root 指针配置
