# 鳴潮：対決 リモート対戦アシスタント

DroidCamのカメラ映像から、クリックした位置にある「鳴潮：対決」のカードを認識し、
カード情報を表示するWindowsデスクトップアプリです。

現在は開発環境とカード画像アセットを準備している段階です。

## 必要環境

- Windows 10またはWindows 11
- Git
- [uv](https://docs.astral.sh/uv/)

Python本体と仮想環境はuvが管理するため、Pythonを別途インストールする必要はありません。

## 開発環境のセットアップ

PowerShellでリポジトリのルートを開き、uvを導入します。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/0.12.19/install.ps1 | iex"
```

PowerShellを開き直した後、依存関係を同期します。

```powershell
uv sync --all-groups
```

## 開発用コマンド

```powershell
# テスト
uv run pytest

# 静的解析
uv run ruff check .
uv run mypy

# フォーマット確認
uv run ruff format --check .
```

## カード画像

カード画像と索引は `assets/cards` に格納されています。取得元と再取得方法は
`assets/cards/README.md` を参照してください。

