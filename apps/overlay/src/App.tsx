import './styles.css';

export function App() {
  return (
    <main className="app-shell">
      <section className="setup-card" aria-labelledby="setup-title">
        <p className="eyebrow">OBS OVERLAY</p>
        <h1 id="setup-title">環境構築が完了しました</h1>
        <p>
          対戦管理機能は次の開発段階で追加します。この画面はReactとViteの起動確認用です。
        </p>
      </section>
    </main>
  );
}
