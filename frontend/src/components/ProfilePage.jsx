function ProfilePage() {
  return (
    <div className="protected-page">
      <h1>User Profile</h1>
      <p>Manage your profile settings and preferences.</p>
      <div className="profile-sections">
        <section>
          <h3>Personal Information</h3>
          <p>Update your personal details here.</p>
        </section>
        <section>
          <h3>Account Settings</h3>
          <p>Change your password and security settings.</p>
        </section>
        <section>
          <h3>Preferences</h3>
          <p>Customize your experience.</p>
        </section>
      </div>
    </div>
  )
}

export default ProfilePage
