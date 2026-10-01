# Match Manager Web（工程2の試作）

Rustの共有対戦コアを実際のWebAssemblyとして読み込み、ライフ・戦況・ターン、Undo、対戦リセットを操作するWeb画面です。
PC側のAPI、WebSocket、OBSには接続しません。
工程2ではメモリ上の履歴だけを使用し、再読み込みで対戦状態は初期化されます。
IndexedDB保存は工程3、共有UIパッケージ化は工程4、インストール・オフライン対応は工程5で追加します。

## 開発環境と準備

既存のNode.js 24、pnpm 11、Rust 1.98.1を利用します。
追加ツールはwasm-pack **0.15.0**、wasm-bindgen **0.2.129**です。
リポジトリのルートで実行します。

```powershell
rustup target add wasm32-unknown-unknown
cargo install wasm-pack --version 0.15.0 --locked --root .tools/wasm-pack
pnpm install --frozen-lockfile
pnpm match-manager-web:dev
```

`http://127.0.0.1:1421` を開きます。
スマホから同じWi-Fiの開発PCに接続して試す場合は、Wasmビルド後に次を実行し、PCのLAN IPと1421番ポートを使います。
接続には開発PCのファイアウォールなどの設定が必要な場合があります。

```powershell
pnpm --filter @wuwatcg/match-manager-web dev --host 0.0.0.0
```

ビルドスクリプトは `.tools/wasm-pack/bin` を優先し、なければPATH上のwasm-packを使います。
バージョン違いはエラーにします。初回Wasmビルド時にはバインディング生成ツールの取得が必要です。
生成される `crates/match-core-wasm/pkg/` はGitに含めず、開発・検証・配布時に再生成します。

## 検証とビルド

```powershell
pnpm match-core:format
pnpm match-core:check
pnpm match-core:test
pnpm match-manager-web:check
pnpm match-manager-web:e2e
pnpm match-manager-web:preview:test
```

ブラウザ検証にはMicrosoft Edgeを使います。
`match-manager-web:e2e` はDesktopのSQLiteアダプターで239コマンドの期待値を生成し、ブラウザ内で動くWasmの各操作後の状態と比較します。
すべてのコマンド種別、no-op、ライフ上下限、Undo、リセット、50戦を超えた履歴保持とUndoの下限を含みます。
不正入力の拒否、Wasm読込失敗からの再試行、操作画面からPC APIへの接続がないことも確認します。

`match-manager-web:preview:test` は配布ビルドを作り、Vite previewで操作画面を検証します。
開発サーバーだけでなく、ハッシュ付きWasmが静的成果物から読み込めることを確認します。
生成したDesktop期待値は `tests/generated/` に置き、Gitには含めません。

```powershell
pnpm match-manager-web:build
pnpm --filter @wuwatcg/match-manager-web preview
```

出力は `apps/match-manager-web/dist/`。公開は後続工程です。
今回の検証はEdge上のスマホ相当の画面サイズで行うものであり、Android/iPhoneの実機確認を意味しません。

## 構成

- `crates/match-core-wasm`: JSON契約で初期状態、コマンド、Undo、履歴境界を返す薄いWasmラッパー。
- `src/matchSession.ts`: 工程2用のメモリ保存アダプター。計算をWasmへ委譲する。
- `src/matchStore.ts`: Zustandで画面状態、起動、エラーを管理する。
- `src/App.tsx`: 既存のDesktopの表示コンポーネントを再利用する。保存先やPC接続処理は取り込まない。
- `tests/e2e`: 実際のブラウザでWasmとUIを検証する。

状態型は現時点でDesktopのTypeScript契約を型として参照し、Rustとの一致は比較テストで確認します。
revisionがJavaScriptの安全な整数範囲を超える状態と、その範囲を超える更新はラッパーが拒否します。

自作部分は[MITライセンス](LICENSE)です。第三者ライセンスは[表記](../../THIRD_PARTY_NOTICES.md)を参照してください。
