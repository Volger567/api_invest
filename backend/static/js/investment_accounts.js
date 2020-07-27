$(document).ready(function() {
  const csrfToken = $('meta[name="csrf-token"]').prop('content')
  // Кнопка добавления нового инвестиционного аккаунта
  $('#add-owned-investment-account-modal-add').on('click', function() {
    let item = $(this)
    item.prop('disabled', true)

    $.post({
      url: '/api/investment-accounts/',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'name': $('#add-owned-investment-account-modal-name').val(),
        'token': $('#add-owned-investment-account-modal-token').val(),
      },
      success: function(){
        window.location.reload()
      },
      error: function(xhr, status, error) {
        item.prop('disabled', false)
        let errors = JSON.parse(xhr.responseText)
        for (let key in errors) {
          if (errors.hasOwnProperty(key))
            $(`#add-owned-investment-account-modal-${key}-error`).text(errors[key])
        }
      },
    });
  })

  // Выбор инвестиционного аккаунта по умолчанию
  let investment_accounts = $('.investment-accounts li');
  investment_accounts.on('click', function(){
    let item = $(this);
    const userPk = $('#request-user').val();
    $.ajax({
      url: `/api/investors/${userPk}`,
      method: 'PATCH',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'default_investment_account': item.data('uuid')
      },
      success: function() {
        window.location.reload()
      }
    })
  })

  // Удаление инвестиционного аккаунта
  $('.remove-investment-account').on('click', function(e){
    e.stopPropagation()
    let parent = $(this).parent()

    $.ajax({
      url: `/api/investment-accounts/${parent.data('uuid')}`,
      method: 'delete',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      error: function(xhr) {
        alert(xhr.responseText)
      },
      complete: function () {
        parent.remove()
      }
    })
  })
})