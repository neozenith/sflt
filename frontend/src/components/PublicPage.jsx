function PublicPage() {
  return (
    <div className="public-page">
      <h1>Public Page</h1>
      <p>This is a public page that anyone can access without authentication.</p>
      <div className="public-content">
        <h2>Features</h2>
        <ul>
          <li>Open to all visitors</li>
          <li>No authentication required</li>
          <li>General information</li>
          <li>Contact details</li>
        </ul>
      </div>
    </div>
  )
}

export default PublicPage
