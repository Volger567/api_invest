$(document).ready(function() {
  const csrfToken = $('meta[name="csrf-token"]').prop('content')

  $('#add-owned-investment-account-modal-add').on('click', function() {
    $.post({
      url: '/api/create-investment-account/',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'name': $('#add-owned-investment-account-modal-name').val(),
        'token': $('#add-owned-investment-account-modal-token').val(),
        'capital_sharing_principle': $('#add-owned-investment-account-modal-capital-sharing-type').val()
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
      }
    });

  })
})