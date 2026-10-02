# Match UI

DesktopとWebのライフ・戦況・ターン表示を共有する内部Reactパッケージです。
コンポーネントには値と操作コールバックを渡します。DB、HTTP、WebSocket、Wasm、OBSには依存しません。
`readOnly` はDesktopのOBSオーバーレイで使います。

```tsx
import { LifeCounter, BattleStatus, TurnManager } from '@wuwatcg/match-ui';
import '@wuwatcg/match-ui/styles.css';
```

`@wuwatcg/match-ui/contracts` はRustのJSON契約に対応する純粋なTypeScript型を公開します。
コアのルールはRustで実行します。DesktopとWebはそれぞれのテストで検証し、両者の動作一致は保証しません。
共通テーマと基本レイアウトは `styles.css`、端末別レイアウトや接続表示は各アプリで管理します。

このパッケージはソースを公開し、各アプリのViteでビルドします。
Desktopのcomposite TypeScriptプロジェクトにも共有ソースを含めています。
ルートから `pnpm match-ui:check` でフォーマット・Lint・型検査を実行します。
操作と読み取り専用表示はDesktopの既存UIテスト、スマホ表示はWebのブラウザテストで検証します。

自作部分は[MITライセンス](LICENSE)です。第三者ライセンスは[表記](../../THIRD_PARTY_NOTICES.md)を参照してください。
