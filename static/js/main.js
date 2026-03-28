alert('main.js is loaded');

document.addEventListener('DOMContentLoaded', function() {

  // Navigation for main Student Login button on homepage
  const studentLoginBtn = document.querySelector('.btn-main');
  if (studentLoginBtn) {
    studentLoginBtn.addEventListener('click', function(e) {
      e.preventDefault();
      window.location.href = '/student-login'; // Correct Flask route
    });
  }

  // Navigation for Admin Login and Guest Login buttons
  const btnSecondarys = document.querySelectorAll('.btn-secondary');
  btnSecondarys.forEach(button => {
    button.addEventListener('click', function(e) {
      e.preventDefault();
      const btnText = button.textContent.trim().toLowerCase();
      
      if (btnText.includes('admin')) {
        window.location.href = '/admin-login'; // Correct Flask route
      }

      if (btnText.includes('query') || btnText.includes('guest')) {
        window.location.href = '/guest-query'; // Corrected route
      }
    });
  });
});
