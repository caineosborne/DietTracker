import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, Dashboard, HistoryDay, Meal, MealEstimate, MealItem, MealPayload, api } from "./api";
import { ArrowIcon, CloseIcon, EditIcon, LeafIcon, PlusIcon, TrashIcon } from "./icons";

type Phase = "waking" | "login" | "ready" | "offline";
type View = "today" | "history";
type Review = { rawText: string; estimate: MealEstimate; requestId: string; mealId?: string; notes?: string };

const number = new Intl.NumberFormat("en-US");

function dayLabel(value: string) {
  return new Intl.DateTimeFormat("en-US", { weekday: "long", month: "long", day: "numeric" }).format(
    new Date(`${value}T12:00:00`),
  );
}

function moveDay(value: string, amount: number) {
  const date = new Date(`${value}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

function localDateTime(iso: string) {
  const date = new Date(iso);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function App() {
  const [phase, setPhase] = useState<Phase>("waking");
  const [username, setUsername] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [view, setView] = useState<View>("today");
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  const loadDashboard = useCallback(async (day?: string) => {
    const data = await api.dashboard(day);
    setDashboard(data);
    return data;
  }, []);

  const start = useCallback(async () => {
    setPhase("waking");
    setError("");
    try {
      await api.health();
      try {
        const signedIn = await api.session();
        setUsername(signedIn.username);
        await loadDashboard();
        setPhase("ready");
      } catch (sessionError) {
        if (sessionError instanceof ApiError && sessionError.status === 401) setPhase("login");
        else throw sessionError;
      }
    } catch {
      setError("The tracker is taking longer than usual to wake up. Your data is safe.");
      setPhase("offline");
    }
  }, [loadDashboard]);

  useEffect(() => {
    void start();
  }, [start]);

  const refresh = async (day?: string) => {
    try {
      await loadDashboard(day ?? dashboard?.selected_day);
    } catch (refreshError) {
      setError(refreshError instanceof Error ? refreshError.message : "Could not refresh the ledger.");
    }
  };

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 3200);
  };

  if (phase === "waking") return <WakeScreen />;
  if (phase === "offline") return <OfflineScreen message={error} retry={start} />;
  if (phase === "login") {
    return (
      <LoginScreen
        onLogin={async (user, password) => {
          const result = await api.login(user, password);
          setUsername(result.username);
          await loadDashboard();
          setPhase("ready");
        }}
      />
    );
  }
  if (!dashboard) return <WakeScreen />;

  return (
    <div className="app-shell">
      <Header
        view={view}
        setView={setView}
        username={username}
        timezone={dashboard.timezone}
        timezones={dashboard.supported_timezones}
        onTimezone={async (timezone) => {
          await api.saveTimezone(timezone);
          await loadDashboard(dashboard.selected_day);
          notify("Time zone updated");
        }}
        logout={async () => {
          await api.logout();
          setDashboard(null);
          setPhase("login");
        }}
      />
      <main>
        {error && <div className="inline-error" role="alert">{error}<button onClick={() => setError("")}>Dismiss</button></div>}
        {view === "today" ? (
          <TodayView dashboard={dashboard} refresh={refresh} notify={notify} setError={setError} />
        ) : (
          <HistoryView dashboard={dashboard} />
        )}
      </main>
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  );
}

function WakeScreen() {
  return (
    <main className="center-screen wake-screen">
      <div className="wake-mark"><LeafIcon /></div>
      <p className="eyebrow">DietTracker</p>
      <h1>Waking your daily ledger</h1>
      <p>The API sleeps between visits to save compute. This usually takes just a moment.</p>
      <div className="pulse-line"><span /></div>
    </main>
  );
}

function OfflineScreen({ message, retry }: { message: string; retry: () => void }) {
  return (
    <main className="center-screen">
      <div className="wake-mark muted"><LeafIcon /></div>
      <p className="eyebrow">Still starting</p>
      <h1>Let’s give it another nudge.</h1>
      <p>{message}</p>
      <button className="primary-button" onClick={retry}>Try waking the API again</button>
    </main>
  );
}

function LoginScreen({ onLogin }: { onLogin: (username: string, password: string) => Promise<void> }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await onLogin(username, password);
    } catch (loginError) {
      setError(loginError instanceof Error ? loginError.message : "Sign-in failed.");
      setBusy(false);
    }
  };
  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand-lockup"><span><LeafIcon /></span> DietTracker</div>
        <div>
          <p className="eyebrow">A private daily practice</p>
          <h1>Notice the day.<br />Then carry on.</h1>
          <p>Meals, movement and weight—kept in one quiet ledger.</p>
        </div>
        <p className="login-footnote">Your API wakes only when you arrive.</p>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <p className="eyebrow">Welcome back</p>
          <h2>Open your ledger</h2>
          <label>Username<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" disabled={busy}>{busy ? "Opening…" : "Sign in"}</button>
        </form>
      </section>
    </main>
  );
}

function Header(props: {
  view: View;
  setView: (view: View) => void;
  username: string;
  timezone: string;
  timezones: string[];
  onTimezone: (timezone: string) => Promise<void>;
  logout: () => Promise<void>;
}) {
  return (
    <header className="site-header">
      <div className="brand-lockup"><span><LeafIcon /></span> DietTracker</div>
      <nav aria-label="Main navigation">
        <button className={props.view === "today" ? "active" : ""} onClick={() => props.setView("today")}>Today</button>
        <button className={props.view === "history" ? "active" : ""} onClick={() => props.setView("history")}>History</button>
      </nav>
      <div className="account-menu">
        <label className="timezone-select"><span>Time zone</span><select value={props.timezone} onChange={(e) => void props.onTimezone(e.target.value)}>{props.timezones.map((zone) => <option key={zone}>{zone}</option>)}</select></label>
        <span className="user-name">{props.username}</span>
        <button className="text-button" onClick={() => void props.logout()}>Sign out</button>
      </div>
      <details className="mobile-account">
        <summary aria-label="Account settings">•••</summary>
        <div>
          <label>Time zone<select value={props.timezone} onChange={(e) => void props.onTimezone(e.target.value)}>{props.timezones.map((zone) => <option key={zone}>{zone}</option>)}</select></label>
          <button onClick={() => void props.logout()}>Sign out</button>
        </div>
      </details>
    </header>
  );
}

function TodayView({ dashboard, refresh, notify, setError }: {
  dashboard: Dashboard;
  refresh: (day?: string) => Promise<void>;
  notify: (message: string) => void;
  setError: (message: string) => void;
}) {
  const [review, setReview] = useState<Review | null>(null);
  const [savingDaily, setSavingDaily] = useState(false);
  const [activeCalories, setActiveCalories] = useState(dashboard.activity?.active_calories ?? 0);
  const [weight, setWeight] = useState(dashboard.weight?.weight_kg ?? dashboard.day_metrics.expected_weight_kg);

  useEffect(() => {
    setActiveCalories(dashboard.activity?.active_calories ?? 0);
    setWeight(dashboard.weight?.weight_kg ?? dashboard.day_metrics.expected_weight_kg);
  }, [dashboard]);

  const run = async (action: () => Promise<void>, success: string) => {
    setSavingDaily(true);
    setError("");
    try {
      await action();
      await refresh();
      notify(success);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "The change could not be saved.");
    } finally {
      setSavingDaily(false);
    }
  };

  return (
    <>
      <section className="today-heading">
        <div>
          <p className="eyebrow">Daily ledger</p>
          <h1>{dashboard.selected_day === dashboard.today ? "Today" : dayLabel(dashboard.selected_day)}</h1>
          {dashboard.selected_day === dashboard.today && <p>{dayLabel(dashboard.selected_day)}</p>}
        </div>
        <div className="day-nav">
          <button aria-label="Previous day" onClick={() => void refresh(moveDay(dashboard.selected_day, -1))}><ArrowIcon className="back" /></button>
          <button onClick={() => void refresh(dashboard.today)} disabled={dashboard.selected_day === dashboard.today}>Today</button>
          <button aria-label="Next day" onClick={() => void refresh(moveDay(dashboard.selected_day, 1))}><ArrowIcon /></button>
        </div>
      </section>

      <section className="today-grid">
        <div className="main-column">
          <MealComposer
            onReview={setReview}
            onSaved={async () => { await refresh(); notify("Meal added to today"); }}
            setError={setError}
            activeCalories={activeCalories}
            setActiveCalories={setActiveCalories}
            savingActivity={savingDaily}
            saveActivity={() => run(() => api.saveActivity(dashboard.selected_day, activeCalories).then(() => undefined), "Active calories updated")}
          />
          <section className="meal-list-section">
            <div className="section-heading"><div><p className="eyebrow">On the table</p><h2>{dashboard.meals.length ? `${dashboard.meals.length} entries` : "Nothing logged yet"}</h2></div><span>{number.format(dashboard.day_metrics.total_calories)} cal</span></div>
            <div className="meal-list">
              {dashboard.meals.length === 0 && <div className="empty-state"><LeafIcon /><p>Start with a plain description of what you ate. The estimate can be reviewed before it becomes part of the day.</p></div>}
              {dashboard.meals.map((meal) => (
                <MealRow
                  key={meal.id}
                  meal={meal}
                  onEdit={() => setReview({ rawText: meal.raw_text, requestId: meal.id, mealId: meal.id, notes: meal.notes, estimate: { items: meal.items, total_calories_low: meal.total_calories_low, total_calories_mid: meal.total_calories_mid, total_calories_high: meal.total_calories_high, consumed_at: meal.timestamp, time_source: "saved", summary_notes: "" } })}
                  onDelete={() => void run(() => api.deleteMeal(meal.id), "Meal removed")}
                />
              ))}
            </div>
          </section>
        </div>

        <aside className="day-sidebar">
          <CaloriePlate total={dashboard.day_metrics.total_calories} goal={dashboard.daily_goal} status={dashboard.day_metrics.status} />
          <div className="metric-pair">
            <Metric label="Active" value={`${number.format(dashboard.day_metrics.active_calories)} cal`} />
            <Metric label="Total burn" value={`${number.format(dashboard.day_metrics.total_burn)} cal`} />
          </div>
          <div className={`net-metric ${dashboard.day_metrics.calorie_balance < 0 ? "surplus" : ""}`}>
            <span>Net difference</span>
            <strong>{dashboard.day_metrics.calorie_balance >= 0 ? "+" : ""}{number.format(dashboard.day_metrics.calorie_balance)} <small>cal</small></strong>
            <p>{number.format(dashboard.day_metrics.total_burn)} burn − {number.format(dashboard.day_metrics.total_calories)} intake</p>
          </div>
          <div className="projection-card">
            <p className="eyebrow">Weight projection</p>
            <strong>{dashboard.day_metrics.expected_weight_kg.toFixed(1)} <small>kg</small></strong>
            <p>{dashboard.day_metrics.weight_direction_label} {dashboard.day_metrics.expected_weight_delta_kg.toFixed(2)} kg today</p>
          </div>
          <details className="daily-inputs">
            <summary>Update weight <ArrowIcon /></summary>
            <form onSubmit={(e) => { e.preventDefault(); void run(() => api.saveWeight(dashboard.selected_day, weight).then(() => undefined), "Weight updated"); }}>
              <label>Weight in kg<input type="number" min="30.1" max="300" step="0.1" value={weight.toFixed(1)} onChange={(e) => setWeight(Number(e.target.value))} /></label>
              <button disabled={savingDaily}>Save weight</button>
            </form>
          </details>
        </aside>
      </section>
      {review && <ReviewDialog review={review} close={() => setReview(null)} saved={async () => { setReview(null); await refresh(); notify(review.mealId ? "Meal updated" : "Meal added"); }} setError={setError} />}
    </>
  );
}

function MealComposer({ onReview, onSaved, setError, activeCalories, setActiveCalories, savingActivity, saveActivity }: {
  onReview: (review: Review) => void;
  onSaved: () => Promise<void>;
  setError: (message: string) => void;
  activeCalories: number;
  setActiveCalories: (value: number) => void;
  savingActivity: boolean;
  saveActivity: () => Promise<void>;
}) {
  const [rawText, setRawText] = useState("");
  const [direct, setDirect] = useState(true);
  const [busy, setBusy] = useState(false);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!rawText.trim()) return;
    setBusy(true);
    setError("");
    try {
      const estimate = await api.estimate(rawText.trim());
      if (direct) {
        await api.createMeal(toPayload(rawText.trim(), estimate, undefined, "", requestId));
        setRawText("");
        setRequestId(crypto.randomUUID());
        await onSaved();
      } else onReview({ rawText: rawText.trim(), estimate, requestId });
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "The meal could not be estimated.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="composer">
      <div className="composer-title"><span><PlusIcon /></span><div><p className="eyebrow">Quick entry</p><h2>What did you eat?</h2></div></div>
      <form onSubmit={submit}>
        <textarea value={rawText} onChange={(e) => { setRawText(e.target.value); setRequestId(crypto.randomUUID()); }} placeholder="A small phở bò tái, around 300 calories…" rows={3} disabled={busy} />
        <div className="composer-actions">
          <label className="switch"><input type="checkbox" checked={!direct} onChange={(e) => setDirect(!e.target.checked)} /><span />Review estimate first</label>
          <button className="primary-button" disabled={busy || !rawText.trim()}>{busy ? "Estimating…" : direct ? "Add meal" : "Estimate meal"}<ArrowIcon /></button>
        </div>
      </form>
      <div className="composer-divider" />
      <form className="activity-entry" onSubmit={(event) => { event.preventDefault(); void saveActivity(); }}>
        <div>
          <span className="activity-icon" aria-hidden="true">↗</span>
          <label htmlFor="active-calories"><strong>Active calories</strong><small>Movement above your resting baseline</small></label>
        </div>
        <div className="activity-control">
          <span>cal</span>
          <input id="active-calories" type="number" min="0" max="10000" step="1" value={activeCalories} onChange={(event) => setActiveCalories(Number(event.target.value))} />
          <button disabled={savingActivity}>{savingActivity ? "Saving…" : "Save activity"}</button>
        </div>
      </form>
    </section>
  );
}

function MealRow({ meal, onEdit, onDelete }: { meal: Meal; onEdit: () => void; onDelete: () => void }) {
  const [confirming, setConfirming] = useState(false);
  const timestamp = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit" }).format(new Date(meal.timestamp));
  return (
    <article className={`meal-row ${meal.is_small_snack_allowance ? "allowance" : ""}`}>
      <time>{timestamp}</time>
      <div className="meal-description"><h3>{meal.raw_text}</h3>{meal.notes && <p>{meal.notes}</p>}{meal.is_small_snack_allowance && <span>Automatic allowance</span>}</div>
      <strong>{number.format(meal.total_calories_mid)} <small>cal</small></strong>
      <div className="row-actions">
        <button aria-label={`Edit ${meal.raw_text}`} onClick={onEdit}><EditIcon /></button>
        {confirming ? <button className="confirm-delete" onBlur={() => setConfirming(false)} onClick={onDelete}>Remove?</button> : <button aria-label={`Delete ${meal.raw_text}`} onClick={() => setConfirming(true)}><TrashIcon /></button>}
      </div>
    </article>
  );
}

function CaloriePlate({ total, goal, status }: { total: number; goal: number; status: string }) {
  const progress = Math.min(total / goal, 1);
  return (
    <div className="calorie-card">
      <p className="eyebrow">Daily intake</p>
      <div className="plate" style={{ "--progress": `${progress * 360}deg` } as React.CSSProperties}>
        <div><strong>{number.format(total)}</strong><span>of {number.format(goal)} cal</span></div>
      </div>
      <div className="calorie-caption"><span>{status}</span><p>{total <= goal ? `${number.format(goal - total)} calories left in today’s guide` : `${number.format(total - goal)} calories over today’s guide`}</p></div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="mini-metric"><span>{label}</span><strong>{value}</strong></div>;
}

function ReviewDialog({ review, close, saved, setError }: { review: Review; close: () => void; saved: () => Promise<void>; setError: (message: string) => void }) {
  const [items, setItems] = useState(review.estimate.items);
  const [total, setTotal] = useState(review.estimate.total_calories_mid);
  const [consumedAt, setConsumedAt] = useState(localDateTime(review.estimate.consumed_at));
  const [notes, setNotes] = useState(review.notes ?? "");
  const [busy, setBusy] = useState(false);
  const update = (index: number, changes: Partial<MealItem>) => setItems((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, ...changes } : item));
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = toPayload(review.rawText, { ...review.estimate, items, consumed_at: new Date(consumedAt).toISOString() }, total, notes, review.requestId);
    try {
      if (review.mealId) await api.updateMeal(review.mealId, payload);
      else await api.createMeal(payload);
      await saved();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "The meal could not be saved.");
      setBusy(false);
    }
  };
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) close(); }}>
      <section className="review-dialog" role="dialog" aria-modal="true" aria-labelledby="review-title">
        <button className="dialog-close" aria-label="Close" onClick={close}><CloseIcon /></button>
        <p className="eyebrow">{review.mealId ? "Correct an entry" : "Check the estimate"}</p>
        <h2 id="review-title">{review.rawText}</h2>
        <div className="estimate-strip"><span><small>Estimated range</small>{number.format(review.estimate.total_calories_low)}–{number.format(review.estimate.total_calories_high)} cal</span><span><small>Time source</small>{review.estimate.time_source.replaceAll("_", " ")}</span></div>
        <form onSubmit={submit}>
          <div className="review-items">
            {items.map((item, index) => (
              <div className="review-item" key={`${index}-${item.name}`}>
                <label>Food<input value={item.name} onChange={(e) => update(index, { name: e.target.value })} required /></label>
                <label>Low<input type="number" min="0" value={item.calories_low} onChange={(e) => update(index, { calories_low: Number(e.target.value) })} /></label>
                <label>Mid<input type="number" min="0" value={item.calories_mid} onChange={(e) => update(index, { calories_mid: Number(e.target.value) })} /></label>
                <label>High<input type="number" min="0" value={item.calories_high} onChange={(e) => update(index, { calories_high: Number(e.target.value) })} /></label>
                <button type="button" aria-label="Remove item" onClick={() => setItems(items.filter((_, itemIndex) => itemIndex !== index))}><TrashIcon /></button>
              </div>
            ))}
          </div>
          <button type="button" className="add-item" onClick={() => setItems([...items, { name: "", calories_low: 0, calories_mid: 0, calories_high: 0, protein_level: "low", confidence: "medium", notes: "", tags: [] }])}><PlusIcon /> Add another item</button>
          <div className="review-fields">
            <label>Consumed at<input type="datetime-local" value={consumedAt} onChange={(e) => setConsumedAt(e.target.value)} required /></label>
            <label>Total calories<input type="number" min="0" step="10" value={total} onChange={(e) => setTotal(Number(e.target.value))} required /></label>
          </div>
          <label>Notes<textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional context or correction" /></label>
          <div className="dialog-actions"><button type="button" className="secondary-button" onClick={close}>Cancel</button><button className="primary-button" disabled={busy || items.length === 0}>{busy ? "Saving…" : review.mealId ? "Save changes" : "Save meal"}</button></div>
        </form>
      </section>
    </div>
  );
}

function toPayload(rawText: string, estimate: MealEstimate, override?: number, notes = "", id?: string): MealPayload {
  return {
    request_id: id ?? crypto.randomUUID(),
    raw_text: rawText,
    items: estimate.items,
    consumed_at: estimate.consumed_at,
    summary_notes: estimate.summary_notes,
    user_total_override: override ?? estimate.total_calories_mid,
    user_notes: notes,
  };
}

function HistoryView({ dashboard }: { dashboard: Dashboard }) {
  const [range, setRange] = useState<"30" | "all">("30");
  const chartData = range === "30" ? dashboard.history.slice(-30) : dashboard.history;
  return (
    <section className="history-page">
      <div className="history-heading"><div><p className="eyebrow">Long view</p><h1>Patterns, not perfection.</h1><p>The ledger treats days with fewer than two entries as neutral, so partial logs do not invent a deficit.</p></div><div className="week-stamp"><span>Last 7 complete days</span><strong>{dashboard.week_metrics.expected_weight_delta_kg.toFixed(2)} kg</strong><small>estimated {dashboard.week_metrics.weight_direction_label}</small></div></div>
      <div className="history-summaries">{dashboard.history_summaries.map((summary) => <article key={summary.label}><p>{summary.label}</p><strong>{number.format(summary.total_intake)}</strong><span>calories in</span><div><b>{summary.calorie_balance >= 0 ? "+" : ""}{number.format(summary.calorie_balance)}</b> net calories</div><small>Expected {summary.expected_weight_kg.toFixed(1)} kg</small></article>)}</div>
      <div className="history-chart-controls">
        <div><span>Graph range</span><small>{range === "30" ? "Last 30 days" : `All ${dashboard.history.length} days`}</small></div>
        <div className="range-toggle" role="group" aria-label="Graph date range">
          <button className={range === "30" ? "active" : ""} aria-pressed={range === "30"} onClick={() => setRange("30")}>30 days</button>
          <button className={range === "all" ? "active" : ""} aria-pressed={range === "all"} onClick={() => setRange("all")}>All</button>
        </div>
      </div>
      <section className="chart-card"><div className="section-heading"><div><p className="eyebrow">{range === "30" ? "Thirty-day rhythm" : "Complete rhythm"}</p><h2>Calories in and out</h2></div><div className="legend"><span className="in">Intake</span><span className="out">Burn</span><span className="net">Net difference</span></div></div><LineChart data={chartData} /></section>
      <section className="chart-card"><div className="section-heading"><div><p className="eyebrow">Weight trajectory</p><h2>Expected and actual weight</h2></div><div className="legend weight-legend"><span className="expected">Expected</span><span className="actual">Actual</span></div></div><WeightChart data={chartData} /></section>
      <section className="history-table-card"><div className="section-heading"><div><p className="eyebrow">Daily record</p><h2>Recent history</h2></div></div><div className="table-scroll"><table><thead><tr><th>Day</th><th>Intake</th><th>Burn</th><th>Net</th><th>Expected</th><th>Actual</th></tr></thead><tbody>{[...dashboard.history].reverse().map((day) => <tr key={day.day}><td>{day.day}</td><td>{number.format(day.total_intake)}</td><td>{number.format(day.total_burn)}</td><td className={day.calorie_balance >= 0 ? "positive" : "negative"}>{day.calorie_balance >= 0 ? "+" : ""}{number.format(day.calorie_balance)}</td><td>{day.expected_weight_kg.toFixed(1)} kg</td><td>{day.actual_weight_kg == null ? "—" : `${day.actual_weight_kg.toFixed(1)} kg`}</td></tr>)}</tbody></table></div></section>
    </section>
  );
}

function LineChart({ data }: { data: HistoryDay[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const width = 920, height = 280;
  const plot = { left: 62, right: 22, top: 30, bottom: 28 };
  const ticks = [-1000, 500, 2000, 3500];
  const min = ticks[0], max = ticks[ticks.length - 1];
  const x = (index: number) => plot.left + (index / Math.max(data.length - 1, 1)) * (width - plot.left - plot.right);
  const y = (value: number) => height - plot.bottom - ((value - min) / Math.max(max - min, 1)) * (height - plot.top - plot.bottom);
  const path = (key: "total_intake" | "total_burn" | "calorie_balance") => data.map((day, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(day[key]).toFixed(1)}`).join(" ");
  if (!data.length) return <div className="empty-state">No history yet.</div>;
  const inspect = (event: React.MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const chartX = ((event.clientX - box.left) / box.width) * width;
    setHovered(Math.max(0, Math.min(data.length - 1, Math.round(((chartX - plot.left) / (width - plot.left - plot.right)) * (data.length - 1)))));
  };
  const selected = hovered == null ? null : data[hovered];
  return <div className="line-chart interactive-chart">
    {selected && <div className="chart-tooltip" style={{ left: `${(x(hovered!) / width) * 100}%`, transform: x(hovered!) / width < .2 ? "translateX(0)" : x(hovered!) / width > .8 ? "translateX(-100%)" : "translateX(-50%)" }}><strong>{selected.day}</strong><span><i className="intake-dot" />Intake <b>{number.format(selected.total_intake)} cal</b></span><span><i className="burn-dot" />Burn <b>{number.format(selected.total_burn)} cal</b></span><span><i className="net-dot" />Net difference <b>{selected.calorie_balance >= 0 ? "+" : ""}{number.format(selected.calorie_balance)} cal</b></span><small>{selected.calorie_balance >= 0 ? "Burn exceeded intake" : "Intake exceeded burn"}</small></div>}
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Calories in, calories burned and net difference over ${data.length} days`} onMouseMove={inspect} onMouseLeave={() => setHovered(null)}>
      <text x={plot.left} y="14" className="axis-title">Calories</text>
      <g className="chart-grid">{ticks.map((tick) => <g key={tick}><line x1={plot.left} y1={y(tick)} x2={width - plot.right} y2={y(tick)} /><text x={plot.left - 9} y={y(tick) + 3} textAnchor="end">{number.format(Math.round(tick))}</text></g>)}</g>
      <line x1={plot.left} y1={y(0)} x2={width - plot.right} y2={y(0)} className="net-zero-line" /><text x={width - plot.right - 4} y={y(0) - 7} textAnchor="end" className="zero-label">0 net</text>
      <line x1={plot.left} y1={y(1900)} x2={width - plot.right} y2={y(1900)} className="goal-line" /><text x={plot.left + 5} y={y(1900) - 7}>1,900 goal</text>
      <path d={path("total_burn")} className="burn-line" /><path d={path("total_intake")} className="intake-line" /><path d={path("calorie_balance")} className="net-line" />
      {selected && <g className="hover-markers"><line x1={x(hovered!)} x2={x(hovered!)} y1={plot.top} y2={height - plot.bottom} /><circle cx={x(hovered!)} cy={y(selected.total_burn)} r="5" className="burn-point" /><circle cx={x(hovered!)} cy={y(selected.total_intake)} r="5" className="intake-point" /><circle cx={x(hovered!)} cy={y(selected.calorie_balance)} r="5" className="net-point" /></g>}
    </svg><div className="chart-dates"><span>{data[0].day}</span><span>{data[data.length - 1].day}</span></div></div>;
}

function WeightChart({ data }: { data: HistoryDay[] }) {
  const [hovered, setHovered] = useState<number | null>(null);
  const width = 920, height = 280;
  const plot = { left: 62, right: 22, top: 30, bottom: 28 };
  const actualPoints = data.map((day, index) => ({ value: day.actual_weight_kg, index })).filter((point): point is { value: number; index: number } => point.value != null);
  const values = [...data.map((day) => day.expected_weight_kg), ...actualPoints.map((point) => point.value)];
  if (!data.length || !values.length) return <div className="empty-state">No weight history yet.</div>;
  const min = Math.floor((Math.min(...values) - .8) * 2) / 2;
  const max = Math.ceil((Math.max(...values) + .8) * 2) / 2;
  const x = (index: number) => plot.left + (index / Math.max(data.length - 1, 1)) * (width - plot.left - plot.right);
  const y = (value: number) => height - plot.bottom - ((value - min) / Math.max(max - min, 1)) * (height - plot.top - plot.bottom);
  const ticks = Array.from({ length: 5 }, (_, index) => min + ((max - min) * index) / 4);
  const expectedPath = data.map((day, index) => `${index ? "L" : "M"}${x(index).toFixed(1)},${y(day.expected_weight_kg).toFixed(1)}`).join(" ");
  const actualPath = actualPoints.map((point, index) => `${index ? "L" : "M"}${x(point.index).toFixed(1)},${y(point.value).toFixed(1)}`).join(" ");
  const inspect = (event: React.MouseEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const chartX = ((event.clientX - box.left) / box.width) * width;
    setHovered(Math.max(0, Math.min(data.length - 1, Math.round(((chartX - plot.left) / (width - plot.left - plot.right)) * (data.length - 1)))));
  };
  const selected = hovered == null ? null : data[hovered];
  return <div className="line-chart interactive-chart weight-chart">
    {selected && <div className="chart-tooltip" style={{ left: `${(x(hovered!) / width) * 100}%`, transform: x(hovered!) / width < .2 ? "translateX(0)" : x(hovered!) / width > .8 ? "translateX(-100%)" : "translateX(-50%)" }}><strong>{selected.day}</strong><span><i className="expected-dot" />Expected <b>{selected.expected_weight_kg.toFixed(1)} kg</b></span><span><i className="actual-dot" />Actual <b>{selected.actual_weight_kg == null ? "Not logged" : `${selected.actual_weight_kg.toFixed(1)} kg`}</b></span>{selected.weight_difference_kg != null && <small>{selected.weight_difference_kg >= 0 ? "+" : ""}{selected.weight_difference_kg.toFixed(1)} kg vs expected</small>}</div>}
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Expected and actual weight over ${data.length} days`} onMouseMove={inspect} onMouseLeave={() => setHovered(null)}>
      <text x={plot.left} y="14" className="axis-title">Weight (kg)</text>
      <g className="chart-grid">{ticks.map((tick) => <g key={tick}><line x1={plot.left} y1={y(tick)} x2={width - plot.right} y2={y(tick)} /><text x={plot.left - 9} y={y(tick) + 3} textAnchor="end">{tick.toFixed(1)}</text></g>)}</g>
      <path d={expectedPath} className="expected-line" /><path d={actualPath} className="actual-line" />
      {actualPoints.map((point) => <circle key={point.index} cx={x(point.index)} cy={y(point.value)} r="3.5" className="actual-history-point" />)}
      {selected && <g className="hover-markers"><line x1={x(hovered!)} x2={x(hovered!)} y1={plot.top} y2={height - plot.bottom} /><circle cx={x(hovered!)} cy={y(selected.expected_weight_kg)} r="5" className="expected-point" />{selected.actual_weight_kg != null && <circle cx={x(hovered!)} cy={y(selected.actual_weight_kg)} r="5" className="actual-point" />}</g>}
    </svg><div className="chart-dates"><span>{data[0].day}</span><span>{data[data.length - 1].day}</span></div></div>;
}

export default App;
