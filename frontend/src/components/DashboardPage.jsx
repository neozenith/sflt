function DashboardPage() {
  return (
    <div className="protected-page">
      <h1>User Dashboard</h1>
      <p>Welcome to your personal dashboard!</p>
      <div className="dashboard-widgets">
        <div className="widget">
          <h3>Recent Activity</h3>
          <p>Your recent actions will appear here.</p>
        </div>
        <div className="widget">
          <h3>Quick Stats</h3>
          <p>View your account statistics.</p>
        </div>
        <div className="widget">
          <h3>Notifications</h3>
          <p>No new notifications.</p>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
