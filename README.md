# 鳴潮：対決 対戦ツール
「鳴潮：対決」の対戦で使用するツール群を開発しています。

## 開発動機
リモート対戦の敷居を下げ、対戦相手が身近にいないプレイヤーでも「鳴潮：対決」を楽しめるようにすることです。

## 対戦管理ツール / Match Manager
プレイヤー二人のライフ・戦況・ターンの管理ができるWindowsデスクトップアプリです。

配信や録画で対戦状況を表示したい場合は、追加機能のOBSオーバーレイを利用できます。

[Web版](apps/match-manager-web/README.md)では、Wasmの共有コアで対戦を操作し、IndexedDBに状態と履歴を保存・復元できます。

PWA(Progressive Web Application)に対応しています。

DesktopとWebは[共有React UI](packages/match-ui/README.md)を利用します。Webはスマホの縦画面・タッチ操作・セーフエリアに対応しています。

## 鳴潮：対決 リモート対戦アシスタント
「鳴潮：対決」のリモート対戦をアシストするWindowsデスクトップアプリです。
- Webカメラ映像から、マウスのドラッグで指定した位置にある「鳴潮：対決」のカードを認識し、
カード情報を表示する
- ライフカウンター
- 戦況(優勢)管理
- アクションフェーズ管理(チャージ/切り替え/レベルアップ)


## ライセンス

match-managerの `apps/match-manager/` 内の自作部分は、[MITライセンス](apps/match-manager/LICENSE)で公開しています。
共有Rustコアの `crates/match-core/` も[MITライセンス](crates/match-core/LICENSE)で公開しています。
Wasmラッパーの `crates/match-core-wasm/` とWeb試作版の `apps/match-manager-web/` も、それぞれのディレクトリに置いたMITライセンスで公開しています。
共有UIの `packages/match-ui/` も[MITライセンス](packages/match-ui/LICENSE)で公開しています。
このライセンスは画像認識アプリの `src/`、`tests/`、リポジトリ直下のファイル、および `assets/cards/` には適用されません。

画像認識アプリ（`src/`、`tests/` など）には現時点でライセンスを付与していません。今後ライセンスを定める場合があります。
カード画像の使用許諾については権利者に確認中です。進捗は[カード画像の説明](assets/cards/README.md)を参照してください。

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
