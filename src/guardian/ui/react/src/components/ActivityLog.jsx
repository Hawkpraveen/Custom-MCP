export function ActivityLog({activity}) {
  return <details className="activity"><summary>Decisions this session <span>{activity.length}</span></summary><div className="activity-content">
    {!activity.length && <p>Your recent decisions will appear here. Nothing is saved in browser storage.</p>}
    <ul>{activity.map((item) => <li key={item.id} className={item.allow ? undefined : "denied"}><span>{item.allow ? "Allowed" : "Blocked"}</span><span>{item.name}</span><time>{item.time}</time></li>)}</ul>
  </div></details>;
}
