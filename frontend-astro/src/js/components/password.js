export const initPasswordWrapper = () => {
  // Password wrapper toggle functionality
  const passwordWrappers = document.querySelectorAll('.password-wrapper')
  passwordWrappers.forEach(passwordWrapper => {
    const toggleBtn = passwordWrapper.querySelector('.password-toggle')
    const passwordInput = passwordWrapper.querySelector('.password-input')
    const eyeIcon = toggleBtn.querySelector('i')
    
    toggleBtn.addEventListener('click', function() {
      const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password'
      passwordInput.setAttribute('type', type)
      eyeIcon.classList.toggle('ri-eye-line')
      eyeIcon.classList.toggle('ri-eye-off-line')
    })
  })

  // Generate random password
  const generatePasswords = document.querySelectorAll(".generate-password")
  if (generatePasswords.length > 0) {
    generatePasswords.forEach(generatePasswordBtn => {
      generatePasswordBtn.addEventListener("click", function () {
        const passwordWrapper = generatePasswordBtn.closest('div').querySelector('.password-wrapper')
        const passwordInput = passwordWrapper.querySelector('.password-input')
        const toggleBtn = passwordWrapper.querySelector('.password-toggle')
        const length = 12
        const charset = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+"
        let password = ""

        for (let i = 0; i < length; i++) {
          password += charset.charAt(Math.floor(Math.random() * charset.length))
        }

        passwordInput.value = password
        // Show password after generating
        passwordInput.setAttribute("type", "text")
        const icon = toggleBtn.querySelector("i")
        icon.classList.remove("ri-eye-off-line")
        icon.classList.add("ri-eye-line")
      })
    })
  }
}