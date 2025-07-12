function AdminPage() {
  return (
    <div className="protected-page">
      <h1>Admin Dashboard</h1>
      <p>This is a protected admin page that requires authentication.</p>
      <div className="admin-content">
        <h2>Admin Tools</h2>
        <ul>
          <li>User Management</li>
          <li>Site Configuration</li>
          <li>Analytics</li>
          <li>Security Settings</li>
        </ul>
      </div>
    </div>
  )
}

export default AdminPage
