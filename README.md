# 鳴潮：対決 リモート対戦アシスタント
「鳴潮：対決」のリモート対戦をアシストするWindowsデスクトップアプリです。
- Webカメラ映像から、マウスのドラッグで指定した位置にある「鳴潮：対決」のカードを認識し、
カード情報を表示する
- ライフカウンター
- 戦況(優勢)管理
- アクションフェーズ管理(チャージ/切り替え/レベルアップ)


画像認識だけ除外した、OBS用対戦管理ツールも開発中です。
環境構築と開発コマンドは
[`apps/overlay/README.md`](apps/overlay/README.md)を参照してください。

# 目的
リモート対戦の敷居を下げ、対戦相手が身近にいないプレイヤーでも「鳴潮：対決」を楽しめるようにすることです。

## ライセンス

OBSオーバーレイの `apps/overlay/` 内の自作部分は、[MITライセンス](apps/overlay/LICENSE)で公開しています。
このライセンスは画像認識アプリの `src/`、`tests/`、リポジトリ直下のファイル、および `assets/cards/` には適用されません。

画像認識アプリ（`src/`、`tests/` など）には現時点でライセンスを付与していません。今後ライセンスを定める場合があります。
カード画像の権利については権利者に確認中です。進捗は[カード画像の説明](assets/cards/README.md)を参照してください。

第三者の素材・依存ライブラリには、それぞれのライセンスが適用されます。


## 開発環境

- Windows 10またはWindows 11
- Git
- [uv](https://docs.astral.sh/uv/)

Python本体と仮想環境はuvが管理するため、Pythonを別途インストールする必要はありません。

### セットアップ

PowerShellでリポジトリのルートを開き、uvを導入します。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/0.12.19/install.ps1 | iex"
```

PowerShellを開き直した後、依存関係を同期します。

```powershell
uv sync --all-groups
```

### 開発用コマンド

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

カード画像と索引は `assets/cards` に格納予定です。
権利関係、利用許諾を確認中です。`assets/cards/README.md` を参照してください。
