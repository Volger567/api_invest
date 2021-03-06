$(document).ready(function() {
  const csrfToken = $('meta[name="csrf-token"]').prop('content')
  // Кнопка добавления нового инвестиционного аккаунта
  $('#add-owned-investment-account-modal-add').on('click', function() {
    let item = $(this)
    item.prop('disabled', true)

    $.post({
      url: '/api/create-investment-account/',
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
        let errors = JSON.parse(xhr.responseText)
        for (let key in errors) {
          if (errors.hasOwnProperty(key))
            $(`#add-owned-investment-account-modal-${key}-error`).text(errors[key])
        }
      },
      complete: function() {
        item.prop('disabled', false)
      }
    });
  })

  // Выбор инвестиционного аккаунта по умолчанию
  let investment_accounts = $('.investment-accounts li');
  investment_accounts.on('click', function(){
    let item = $(this);
    $.post({
      url: '/api/default-investment-account/',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'value': item.data('uuid')
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

    $.post({
      url: '/api/remove-investment-account/',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'value': parent.data('uuid')
      },
      complete: function () {
        parent.remove()
      }
    })
  })
})