# Match Manager Web（工程3まで実装）

Rustの共有対戦コアを実際のWebAssemblyとして読み込み、ライフ・戦況・ターン、Undo、対戦リセットを操作するWeb画面です。
PC側のAPI、WebSocket、OBSには接続しません。
工程3ではIndexedDB（Dexie）に状態と操作履歴を保存し、再読み込み後も対戦を継続できます。
保存先はブラウザ・端末・オリジンごとに独立します。同じブラウザの同じオリジンを開いた複数タブでは状態を共有します。
共有UIパッケージ化は工程4、インストール・オフライン対応は工程5で追加します。

## 保存と履歴

- ライフ・戦況・ターン・使用済みアクションとUndo履歴を復元します。
- 状態が変わった操作のみを履歴に記録し、進行中を含む直近50戦を保持します。保持範囲外の対戦へはUndoできません。
- 状態、履歴、保持境界の更新を一つのトランザクションで保存します。失敗した操作は画面へ反映しません。
- 連続操作は呼出順に処理し、別タブとの更新はIndexedDBトランザクションで直列化します。Dexie liveQueryで保存完了した状態を画面へ通知します。
- 保存失敗は画面に表示し、すでに待機していた後続操作が成功してもエラーを残します。後から改めて行った操作が成功するとエラーを解除します。
- DBのスキーマ・データ形式と保存状態を検証し、未対応の新しい形式や破損データは自動リセットしません。

DB名は `wuwa-tcg-match-manager`、Dexieスキーマバージョンは1、データ形式バージョンは1です。
`records` に現在状態とUndoのbaseline、`history` に各操作と操作後の状態を保存します。
過去の工程2はメモリだけで動いていたため、工程2の画面内の状態を移行する処理はありません。

ブラウザのデータ削除や保存領域の回収で状態が失われる場合があります。
`navigator.storage.persist()` を補助的に要求しますが、許可は保証せず、拒否されても通常の保存は続けます。
保存が使えない場合に、保存されないメモリモードへ自動的に切り替えることはありません。
JSONのエクスポート・インポート、端末間同期は未実装です。

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
`match-manager-web:e2e` はDesktopのSQLiteアダプターで239コマンドの期待値を生成し、ブラウザ内で動くWasmとIndexedDBの各操作後の状態と比較します。途中でDBを閉じて再開する復元も含みます。
すべてのコマンド種別、no-op、ライフ上下限、Undo、リセット、50戦を超えた履歴保持とUndoの下限を含みます。
不正入力の拒否、Wasm読込失敗からの再試行、操作画面からPC APIへの接続がないことも確認します。
保存・復元、100回の連続操作、複数タブからの同時更新、容量不足・Undo・履歴削除の失敗時ロールバック、破損データ・未対応形式の保護を実際のIndexedDBで検証します。

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
- `src/matchDatabase.ts`: IndexedDBのスキーマとデータ形式。
- `src/matchSession.ts`: IndexedDB保存アダプター。計算をWasmへ委譲し、保存トランザクション・操作キュー・更新通知を扱う。
- `src/matchStore.ts`: Zustandで画面状態、起動、エラーを管理する。
- `src/App.tsx`: 既存のDesktopの表示コンポーネントを再利用する。保存先やPC接続処理は取り込まない。
- `tests/e2e`: 実際のブラウザでWasmとUIを検証する。

状態型は現時点でDesktopのTypeScript契約を型として参照し、Rustとの一致は比較テストで確認します。
revisionがJavaScriptの安全な整数範囲を超える状態と、その範囲を超える更新はラッパーが拒否します。

自作部分は[MITライセンス](LICENSE)です。第三者ライセンスは[表記](../../THIRD_PARTY_NOTICES.md)を参照してください。
