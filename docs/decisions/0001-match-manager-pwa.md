# Match Manager PWAの技術スタックとホスティング

- 決定日: 2026-10-01
- 状態: 採用（共有コア・UI・永続化・PWA・配信設定を実装。公開環境とAndroid/iPhone実機での検証は未確認）
- 最終更新: 2026-10-02
- 初期開発ブランチ: `codex/match-manager-pwa-architecture`

## 目的と初期スコープ

スマートフォン1台で両プレイヤーのライフ、戦況、ターンを管理するPWAを提供する。
Undo、対戦リセット、再起動後の復元を含め、初回読み込みとオフライン用資産の保存完了後は通信なしで使えるようにする。
WebにはOBS連携を含めない。ログイン、クラウド保存、端末間同期、対戦ルームは初期スコープに含めない。

DesktopとWebは同じ対戦ルールを使用し、保存先と実行環境を分離する。
両者の保存データはそれぞれ独立しており、共通コアを使うこと自体は同期を意味しない。

## 採用技術

| 領域             | 採用技術                                              | 選定理由                                                             |
| ---------------- | ----------------------------------------------------- | -------------------------------------------------------------------- |
| 共通の対戦コア   | Rustの独立crate                                       | 既存の対戦ロジックを移し、DesktopとWebで単一の実装を使える           |
| ブラウザ向けコア | WebAssembly、wasm-bindgen、wasm-pack                  | Rustコアをブラウザで実行する薄いアダプターを生成できる               |
| 画面             | React、TypeScript、Vite                               | 既存のコンポーネントと開発環境を再利用できる                         |
| UIの状態管理     | Zustand                                               | 保存・実行アダプターから受け取った状態を画面に反映する               |
| Webの永続化      | IndexedDB、Dexie                                      | 非同期トランザクション、履歴の検索、スキーマのバージョン管理を扱える |
| PWA              | vite-plugin-pwa、Workbox（generateSW）                | Manifest、オフライン用キャッシュ、更新通知をViteのビルドに組み込める |
| Desktop          | 現行のTauri、Rust、SQLite、Axum                       | 保存先とOBS用のHTTP/WebSocketをDesktop側に残せる                     |
| 検証             | Rustの単体テスト、Vitest、Testing Library、Playwright | 対戦ルール、UI、保存・復元、オフライン動作を段階ごとに検証できる     |
| パッケージ管理   | 現行のpnpm workspace                                  | 既存リポジトリ内でWebアプリと共有UIを管理できる                      |
| ビルド・配布     | GitHub Actions、Wrangler                              | Rust/WasmとWebを同じCIでビルドし、静的成果物を配信できる             |
| ホスティング     | Cloudflare Workers Static Assets                      | HTTPSで静的PWAを配信でき、対戦用バックエンドを必要としない           |

Reactなど既存の依存バージョンは原則維持する。新規依存の具体的なバージョンは導入時に互換性を確認してロックする。
PWAには `vite-plugin-pwa` 1.3.0と `workbox-window` 7.4.1を固定して導入し、既存のVite 8.3.1で配布ビルドを確認した。
Rust/Wasmは固定したwasm-pack 0.15.0とwasm-bindgen 0.2.129でビルドする。

## 共通コアの境界

```mermaid
flowchart TB
    core["match-core / Rust<br/>対戦状態・コマンド・ルール・履歴方針"]
    core --> desktop["Desktop / Tauri・Rust"]
    core --> wasm["match-core-wasm / wasm-bindgen"]
    wasm --> web["Web / React PWA"]
    desktop --> sqlite[(SQLite)]
    desktop --> obs["Axum / OBS連携"]
    web --> idb[("IndexedDB / Dexie")]
    hosting["Cloudflare Workers Static Assets"] -. "HTML・JS・CSS・Wasmの配信" .-> web
```

共通コアの切り出しは、既存の `apps/match-manager/src-tauri/src/match_state.rs` を出発点とした。
ここにあった初期ライフ、ライフの範囲、戦況、ターン進行、アクションの状態遷移を共有Rustコアへ移した。
当初 `match_store.rs` にあったUndoと直近50戦の履歴保持も、共通コアの計算と各環境の保存アダプターに分けた。

共通コアには次を置く。

- 対戦状態、コマンド、入力の検証、初期値、状態遷移。
- Undoで復元する状態とrevisionの更新規則。
- 状態が変化しないコマンドでは履歴を増やさない規則。
- リセットが新しい対戦になる条件と、進行中を含む直近50戦の保持方針。
- 保存データの検証と、Desktop/Webで共有するシリアライズ契約。

コアはDB、HTTP、WebSocket、React、Tauri、ブラウザAPIに依存しない。
Undoの復元候補や履歴削除境界を計算する純粋な関数を提供し、履歴の読込・書込は保存アダプターが担当する。
SQLiteの既存スキーマと履歴を維持できる形で移行し、DB構造をWebに合わせて作り直すことはしない。

コマンド処理では、候補状態を計算し、状態と履歴を同一トランザクションで保存した後にUIへ反映する。
保存失敗時に画面だけ先に進むことを防ぐ。Webの連続タップはキューで直列処理する。
複数タブの同時操作は、IndexedDBトランザクション内で最新状態を読み、revisionを照合し、他の画面にも変更を通知する。

WebAssemblyの境界は、まず既存のJSON契約を受け渡す薄いラッパーにする。
コマンドや状態のTypeScript型はRust契約からの生成を検討し、少なくとも契約テストでズレを検出する。
revisionのRust `u64` とJavaScriptの安全な整数範囲の違いも、境界で明示的に検証する。
Rustのpanicで通常の入力エラーを処理せず、検証エラーを結果として返す。

### 共通コア方式の比較

| 方式                                               | 評価                                                                 |
| -------------------------------------------------- | -------------------------------------------------------------------- |
| RustコアをDesktopで直接利用し、WebでWasmとして利用 | 採用。既存ロジックとテストを活かし、両環境のルールを一本化できる     |
| TypeScriptへコアを移す                             | Webは簡単になるが、DesktopのRustサーバーとの責務を作り直す必要がある |
| RustとTypeScriptで同じルールを別々に実装           | 更新のたびに差分が生じるため採用しない                               |

Wasmには追加のビルド工程、初期化、キャッシュ管理が必要になる。
今回の採用理由は計算速度ではなく、既存のRust実装を共通利用できることにある。
最初に小さな実証で、iPhone/Androidでの読込・操作・オフライン起動とビルド手順を確認する。

## ディレクトリ構成

```text
crates/
  match-core/          # 純粋なRustの対戦ロジック
  match-core-wasm/     # ブラウザ向けの薄いラッパー
packages/
  match-ui/            # ライフ・戦況・ターンの共有Reactコンポーネント
apps/
  match-manager/       # 既存Desktopアプリ、SQLite、OBS連携
  match-manager-web/   # PWA、IndexedDB、Web向け操作・更新通知
```

共有UIにはDBや接続処理を入れず、値と操作コールバックを渡す。
DesktopのOBS URL、接続ステータスと、Webのオフライン準備・更新通知は各アプリの画面で扱う。
Webは既存の `127.0.0.1:38471` のAPIやWebSocketを呼ばない。

pnpm workspaceに `apps/*` と `packages/*` を含め、共有RustコアとWasmラッパーは `crates/Cargo.toml` のworkspaceで管理する。
DesktopのCargoプロジェクトとリリースは独立して維持する。
共有部分とWebの自作コードには各ディレクトリのMITライセンスを適用する。

## オフライン・保存・更新

Manifestには安定したid、start_url、scope、standalone表示、アイコンを設定する。
JS/CSSだけでなくWasm、アイコンなど起動に必要な資産をすべて同一オリジンで配信し、プリキャッシュ対象に含める。
外部CDNのランタイム読み込みに依存しない。
オフライン準備完了を表示し、それ以前の初回アクセスには通信が必要であることが分かるようにする。

更新方式は `registerType: 'prompt'` とし、対戦中に自動再読み込みしない。
「更新する」を押すと新規操作を停止し、受付済みの保存キューと画面への保存結果反映を待つ。
保存エラーがある場合は更新を中止し、対戦操作へ戻る。
Web LocksとBroadcastChannelで同じオリジンのタブを調整し、すべてのタブの保存完了後に新Service Workerを有効化して再読み込みする。
応答しないタブがある場合は15秒で更新準備を中止する。調整APIが使えない場合は更新ボタンからの適用を中止し、すべてのタブを閉じて開き直す方法を案内する。
旧プリキャッシュはWorkboxで整理する。現在のDBスキーマと保存形式はバージョン1のままで、今回のPWA対応ではマイグレーションを追加していない。
将来保存形式を変更する際は、旧版からのマイグレーションと複数タブの互換性を別途検証する。
データが復元できない場合に、無言で初期状態へ上書きしない。
DBにはスキーマとコアのデータ形式のバージョンを持たせ、将来の更新を検証可能にする。

IndexedDBは端末・ブラウザ・オリジンごとの保存であり、永続保存の保証ではない。
保存容量不足や書込失敗を画面に表示する。`navigator.storage.persist()` による永続保存の許可は要求しない。
対戦状態とUndo履歴は長期保管を必須としないため、容量不足などによるブラウザの自動削除を許容する。
自動削除はこのアプリの保存量が少なくても起こり得る。直近50戦の保持制限は、操作履歴数や保存容量の厳密な上限ではない。
保存領域の回収でオフライン用キャッシュも失われた場合はオンラインで再度開き、DB全体が削除された場合は初期状態から再開する。
既に得た永続保存の許可を取り消す処理は行わない。
履歴を長期保存したい場合のJSONエクスポート・インポートは後続機能とする。
本番オリジンを変更すると保存データは自動移行しないため、URLは初回公開前に固定する。

## ホスティングの決定

**Cloudflare Workers Static Assetsを採用する。**

Workersという名称でも、この構成ではサーバー側の対戦処理やWorkerスクリプトは作らない。
Viteで生成したHTML、JS、CSS、Wasm、Manifest、Service Workerを配信する。
Cloudflare公式資料では、静的資産へのリクエストは無料・無制限で、資産保存にも追加料金はない。
Workerスクリプト実行、ビルドサービス、独自ドメイン取得は別の条件なので、静的配信の料金と混同しない。

| 候補                             | 判断                                                                                                            |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Cloudflare Workers Static Assets | 採用。静的配信、ヘッダー設定、Wranglerからの配布を一つの環境で扱える                                            |
| Cloudflare Pages                 | PWAの配信は可能。今回はWorkers Static Assetsに配布先を統一する                                                  |
| GitHub Pages                     | 配信は可能。公開サイト1GB、月100GBのソフトな帯域上限があり、PWA用の配信ヘッダーを設定できるCloudflareを優先する |

初回公開にはCloudflareアカウント、配布先の作成、GitHub Actions用のAPIトークンが必要になる。
配布先の設定名は `wrangler.jsonc` の `wuwa-tcg-match-manager-web`。実際の公開URLはGitHub ActionsのDeployログまたはSummaryで確認する。
最初はHTTPSの `workers.dev` を利用できる。独自ドメインを使う場合は初回公開前に決める。
設定ファイルの実装と本番公開の確認は区別する。本書には公開環境でのヘッダー・インストール・オフライン起動の確認結果をまだ記録していない。

### 配布手順の方針

1. GitHub Actionsで既存の固定Node/pnpm/Rustツールチェーンを用意する。
2. `wasm32-unknown-unknown` ターゲットを追加し、固定したwasm-packで `--target web` のバインディングを生成する。
3. 共通コア、共有UI、Webのチェックと永続化E2E・配布ビルドのテストを実行する。WebリリースにはDesktop/Tauriのビルドを含めない。
4. Wasmを含む `apps/match-manager-web/dist` をWranglerで配布する。
5. 本番配布は手動起動から始める。プレビュー配布は本番と別のオリジンで検証する。

Cloudflareで再ビルドせず、CIで検証した成果物をアップロードする。
`apps/match-manager-web/public/_headers` はビルド時に `dist/_headers` へコピーされる。
HTML、Service Worker、Manifestは `Cache-Control: no-cache`、`/assets/*` のハッシュ付き資産は `public, max-age=31536000, immutable` とする。
Vite previewはこのCloudflare用ヘッダー設定を適用しないため、公開後に実際のレスポンスを確認する。
WasmのContent-Type、Service Workerのscope、HTTPSでのインストールとオフライン起動を配布後に確認する。
初期画面は単一URLとし、`wrangler.jsonc` の `not_found_handling: "none"` で存在しないJS/WasmにHTMLを返さない。
公開・確認の手順は[Web版README](../../apps/match-manager-web/README.md#github-actionsから公開する)を参照する。

## 実装順と完了条件

1. Rustコアを切り出し、Desktopで既存の対戦・Undo・履歴保存が維持されることを確認する。
2. Wasmラッパーと最小Web画面を作り、同じコマンド列でDesktop/Webの状態が一致することを確認する。
3. IndexedDBアダプターを実装し、保存・復元、Undo、50戦保持、連続操作、書込失敗を検証する。
4. UIを共有化し、スマホの縦画面、タッチ操作、セーフエリアに対応する。
5. PWAのキャッシュと更新通知を追加し、初回キャッシュ後の機内モード・再起動・更新後の状態復元を確認する。
6. GitHub ActionsとWranglerを設定し、本番URLを固定して公開する。

現在のブラウザ自動検証はPlaywrightとMicrosoft Edgeで行っている。
PlaywrightのWebKit、Android ChromeとiPhone Safari・ホーム画面起動での確認は今後の検証項目とする。
ブラウザの模擬モバイル表示だけをもって、iOSのPWA動作を確認済みとはしない。
工程1では `crates/match-core/` を実装し、Desktopからpath依存で利用する。
共有crateは `crates/Cargo.toml` のworkspaceで管理し、DesktopのCargoプロジェクト、lockfile、targetパス、release profileは維持する。
工程2では `crates/match-core-wasm/` と `apps/match-manager-web/` を実装する。
WasmラッパーはJSON契約とrevisionの安全な整数範囲を検証し、Webのメモリアダプターが履歴を管理する。
DesktopのSQLiteアダプターで生成した239コマンドの操作列と、ブラウザ内で動作するWasmの各状態を比較する。
工程2時点のDesktop UI直接参照は工程4で共有UIパッケージへ置き換えた。
PWAと配信設定の実装・ローカル検証の結果は下記の2026-10-02の記録を参照する。Android/iPhoneの実機検証は未実施。

工程2の検証結果: Rustの32テスト、Clippy、フォーマット・Webの型検査とLintを通過。
Edgeで239操作のDesktop/Web状態一致とWebの4テストを確認し、静的配布ビルドでも2テストを通過した。
Wasm読込失敗後の再試行、PC APIへ接続しない動作、再読み込み時の試作版の初期化を含む。

工程3ではメモリアダプターをIndexedDB/Dexieに置き換える。
DBスキーマと保存データ形式はバージョン1。現在状態・Undoのbaselineは `records`、操作後のスナップショットは `history` に保存する。
Wasm初期化はトランザクション開始前に行い、計算と保存は同一トランザクション内で実行する。
保存完了前にはUIを更新せず、no-opは履歴に追加しない。Undo・リセット・50戦境界の削除も原子的に保存する。
連続操作はキューに入れ、複数タブからの操作はトランザクション内で最新revisionを読んで計算する。
Dexie liveQueryで各画面へ更新を通知する。端末間のクラウド同期は行わない。
起動時に保存データと履歴を検証し、破損・未対応形式の場合はデータを変更せずエラーにする。
工程3では永続保存の許可要求を補助的に行っていたが、2026-10-02に自動削除を許容する方針へ変更し、要求を削除した。保存APIが利用できない場合や容量不足を画面に表示し、保存されないメモリへの自動フォールバックはしない。

工程3の検証結果: Edgeで15テスト、静的配布ビルドで5テストを通過。
239操作のDesktop/IndexedDB状態一致、途中のDB再開、100回の連続操作、複数タブの同時操作を確認した。
容量不足、Undo・保持境界の削除失敗のロールバック、破損・新しいDB形式の保護、連続操作中の保存エラー表示も含む。
Webの型検査・Lint・フォーマット、Rustの14テストとClippyも通過した。

工程4では `packages/match-ui/` にライフ・戦況・ターンのReactコンポーネント、共通テーマ・レイアウト、JSON契約のTypeScript型を移した。
DesktopとWebはworkspace依存で利用し、保存処理、通信、OBSは各アプリに残す。共有UIの自作部分はMITライセンスとする。
Webでは縦画面でも両者のライフを横並びにし、ボタンのタッチ領域を44px以上に確保する。
`viewport-fit=cover` とセーフエリアの余白、縦スクロール、動きを減らす設定に対応する。
幅320・390・430pxのタッチ対応モバイル表示で、横へのはみ出し、連続タップ、Undo、保存・復元を検証する。
セーフエリアはCSS変数へ余白を注入してレイアウトを検証する。実機でのノッチ・ホームインジケーターの確認は未実施。

工程4の検証結果: 共有UI・Desktop・Webの型検査、Lint、フォーマットが通過した。
Desktopの7単体テスト・2ブラウザテスト、Webの21ブラウザテスト・静的配布ビルドの11テストが通過した。
DesktopとWebの配布ビルド、OBSオーバーレイの背景透過・読み取り専用表示も確認した。

### 2026-10-02: Webの検証をDesktopから独立させる

WebではDesktopとの動作一致を保証しない。通常のCIとWebリリースでは、Webの永続化E2Eと配布成果物のテストを実行する。
DesktopのSQLiteから比較データを生成するテストと生成コマンドを削除し、Webの検証からDesktop/Tauriのビルド依存を外す。
Wasmの不正入力拒否、IndexedDBの保存・復元・同時更新・ロールバック、操作画面とモバイル表示のテストは継続する。
上記のDesktop/Web比較結果は、方針変更前の各工程で実施した検証の記録として残す。

### 2026-10-02: PWAと配信設定を実装する

Viteの `generateSW` でManifestとService Workerを生成し、HTML、JS、CSS、Wasm、アイコンをプリキャッシュする。
Manifestのid・start_url・scopeは `/`、表示モードは `standalone` とする。
既存のDesktop用512pxアイコンから192px・512px・Maskable用・Apple用の画像を用意した。
Service Worker登録はReactのStrictModeの外で一度だけ行い、開発サーバーでは無効にする。
保存状況とオフライン準備完了を別のアイコンで表示し、更新検出と登録失敗は通知する。
保存完了を待つ更新処理、複数タブの調整、保存エラー時の中止と操作再開、15秒の待機タイムアウトを実装した。

検証結果: Edgeの開発サーバー向け23テストと配布ビルド向け21テスト、Webのフォーマット・Lint・型検査・配布ビルドが通過した。
通信を切った状態での再読み込みと対戦復元、版Aから版Bへの更新、保存中の操作停止、更新後のUndo復元、別タブの保存待ち・保存失敗・応答待ちタイムアウトを確認した。
更新テストは同じアプリ資産を使い、HTMLとService Workerのプリキャッシュrevisionを切り替えるローカル配信で行った。将来のDB形式変更を検証したものではない。

GitHub Actionsの手動リリースとWranglerの静的配信設定は実装済み。
Cloudflare用の `_headers` がビルド成果物へ完全一致でコピーされ、Service Workerのプリキャッシュ対象に入らないことを確認した。
Cloudflareでの実レスポンスとAndroid/iPhoneのホーム画面追加・機内モード再起動は未確認であり、ローカルのEdge検証と区別する。

## 参照資料

2026-10-01に公式資料を確認した。利用料金・制限・対応バージョンは導入時にも再確認する。

- [wasm-pack buildと出力ターゲット](https://wasm-bindgen.github.io/wasm-pack/book/commands/build.html)
- [DexieとReact](https://dexie.org/docs/Tutorial/React)
- [Vite PWAの更新通知](https://vite-pwa-org.netlify.app/guide/prompt-for-update)
- [PWAのインストール要件](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)
- [ブラウザの保存容量とデータ削除](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)
- [Cloudflare Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- [Static Assetsの料金と制限](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/)
- [GitHub Pagesの制限](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)
