# Match Manager Web（工程5のPWA登録・更新まで実装）

Rustの共有対戦コアを実際のWebAssemblyとして読み込み、ライフ・戦況・ターン、Undo、対戦リセットを操作するWeb画面です。
PC側のAPI、WebSocket、OBSには接続しません。
工程3ではIndexedDB（Dexie）に状態と操作履歴を保存し、再読み込み後も対戦を継続できます。
保存先はブラウザ・端末・オリジンごとに独立します。同じブラウザの同じオリジンを開いた複数タブでは状態を共有します。
工程4でDesktopとWebの表示を `packages/match-ui` に共有化しました。
工程5ではManifest、インストール用アイコン、Wasmを含むオフラインキャッシュとService Worker登録を追加しています。
配布ビルドでキャッシュが完了すると、見出し横のアイコンで「オフラインで利用できます」と表示します。
初回アクセスとキャッシュ完了までは通信が必要です。開発サーバーではService Workerを登録しません。
更新検出時は「更新する」と「あとで」を表示し、通知だけでは再読み込みしません。
「更新する」を押すと対戦操作を停止し、受付済みの保存処理がすべて完了してから新しい版を適用します。
保存エラーがある場合は更新を中止し、対戦操作へ戻ります。更新後は対戦状態とUndo履歴を復元します。
同じオリジンのタブはWeb LocksとBroadcastChannelで保存完了を調整し、更新を適用した後に各タブを再読み込みします。
応答しないタブがある場合は15秒で更新準備を中止します。保存エラーを解消し、応答しないタブを閉じてから再試行してください。
調整APIが使えない環境では更新ボタンからの適用を中止し、すべてのタブを閉じて開き直す方法を案内します。
DBスキーマと保存形式は変更していません。
Android/iPhoneでのインストールとオフライン起動の実機確認は未実施です。

## スマートフォンの操作画面

縦画面でも両者のライフを横並びで表示し、増減ボタンを数値の下に配置します。
すべてのボタンは44px以上のタッチ領域を持ち、連続タップを保存キューで処理します。
保存状況はタイトル横のアイコン、保存についての説明はInfoアイコンのツールチップにまとめています。
ツールチップはタップ・ホバー・キーボードで開き、外側のタップやEscapeで閉じます。
ターン内行動は横3列に並べ、ターン終了はセクションの最下部に配置します。
幅320px・高さ700pxと幅390/430px・高さ844pxでは主要操作が一画面に収まることを検証します。
画面がさらに小さい場合や文字拡大・大きいセーフエリアがある場合は縦スクロールで操作できます。
`viewport-fit=cover` と `env(safe-area-inset-*)` でノッチ・画面端・ホームインジケーター分の余白を確保します。
ブラウザの拡大操作を禁止せず、動きを減らす設定にも対応します。

Edgeのタッチ対応モバイル表示で幅320・390・430pxを検証します。
セーフエリアの検証ではCSS変数に余白を注入してレイアウトを確認しており、実際のiOSの余白検出は実機確認が必要です。

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
pnpm match-ui:check
pnpm match-manager-web:check
pnpm match-manager-web:e2e
pnpm match-manager-web:preview:test
```

ブラウザ検証にはMicrosoft Edgeを使います。
`match-manager-web:e2e` はブラウザ内で動くWasmとIndexedDBを使い、Webの操作と永続化を検証します。Desktopのビルドや比較データの生成は不要です。
不正入力の拒否、Wasm読込失敗からの再試行、操作画面からPC APIへの接続がないことも確認します。
保存・復元、100回の連続操作、複数タブからの同時更新、容量不足・Undo・履歴削除の失敗時ロールバック、破損データ・未対応形式の保護を実際のIndexedDBで検証します。

`match-manager-web:preview:test` は配布ビルドを作り、Vite previewで操作画面を検証します。
開発サーバーだけでなく、ハッシュ付きWasmが静的成果物から読み込めることを確認します。
Service Worker登録、通信を切った状態での再読み込み、登録失敗の通知も検証します。
更新の検証では同じオリジンで版Aと版BのHTML・Service Workerを切り替えて配信し、保存待ち・複数タブの更新・保存失敗時の中止・待機タイムアウトを確認します。

```powershell
pnpm match-manager-web:build
pnpm --filter @wuwatcg/match-manager-web preview
```

出力は `apps/match-manager-web/dist/`。Cloudflareへの公開手順は次の節を参照してください。
今回の検証はEdge上のスマホ相当の画面サイズで行うものであり、Android/iPhoneの実機確認を意味しません。

## GitHub Actionsから公開する

`.github/workflows/match-manager-web-release.yml` の **Match manager Web release** を手動実行し、Cloudflare Workers Static Assetsへ公開します。
公開先はリポジトリ直下の `wrangler.jsonc` にある `wuwa-tcg-match-manager-web` です。

### リリースする

Github Actionの手動リリースです。

1. GitHubリポジトリの **Actions** を開きます。
2. **Match manager Web release** を選択します。
3. **Run workflow** を開き、公開するブランチを選びます。通常はデフォルトブランチを使います。
4. **Run workflow** を押します。選択したブランチのコードが検証・ビルドされ、成功すると本番URLの内容が更新されます。
5. `release` が成功したら、実行のSummaryまたはDeployステップのログに表示される公開URLを確認します

## 構成

- `crates/match-core-wasm`: JSON契約で初期状態、コマンド、Undo、履歴境界を返す薄いWasmラッパー。
- `src/matchDatabase.ts`: IndexedDBのスキーマとデータ形式。
- `src/matchSession.ts`: IndexedDB保存アダプター。計算をWasmへ委譲し、保存トランザクション・操作キュー・更新通知を扱う。
- `src/matchStore.ts`: Zustandで画面状態、起動、エラーを管理する。
- `src/App.tsx`: 共有UIを利用し、Webの保存状況・エラー・操作を扱う。
- `packages/match-ui`: DesktopとWebで共有するライフ・戦況・ターンのコンポーネントとテーマ、JSON契約のTypeScript型。
- `tests/e2e`: 実際のブラウザでWasmとUIを検証する。

状態型は共有パッケージの純粋な型を参照します。Desktopとの動作一致は保証せず、Webの永続化E2Eと配布ビルドのテストで検証します。
revisionがJavaScriptの安全な整数範囲を超える状態と、その範囲を超える更新はラッパーが拒否します。

自作部分は[MITライセンス](LICENSE)です。第三者ライセンスは[表記](../../THIRD_PARTY_NOTICES.md)を参照してください。
