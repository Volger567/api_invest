$(document).ready(function() {
  let timer;
  const maxCapital = $('#total-capital').val();
  const csrfToken = $('meta[name="csrf-token"]').prop('content')
  $('#add-co-owners').on('keyup', function(){
    let item = $(this)
    let investorsElement = $('#found-investors')
    if (timer)
      clearTimeout(timer)
    timer = setTimeout(function(){
      if (!item.val()) {
        investorsElement.text('')
        return
      }
      $.get({
        url: '/api/search-investors/',
        dataType: 'json',
        headers : {
          'X-CSRFTOKEN': csrfToken
        },
        data: {
          'username': item.val()
        },
        success: function(data) {
          investorsElement.text('')
          data.forEach(function(user){
            investorsElement.append(`<button class="btn btn-primary m-1 add-co-owner-btn">${user}</button>`)
          })
        },
      })
    }, 500)
  })

  $(document).on('click', '.add-co-owner-btn', function() {
    let username = $(this).text()
    let coOwnersElement = $('#co-owners');
    $.post({
      url: '/api/co-owners/',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'username': username
      },
      success: function () {
        window.location.reload()
      }
    })
  })

  $('.co-owner-capital input').change(function() {
    let item = $(this);
    let currentSum = parseFloat(item.val());
    let sum = 0;
    $('.co-owner-capital input').not(item).each(function() {
      sum += parseFloat($(this).val())
    })
    let totalSum = sum + currentSum;
    const maxSum = parseFloat($('#total-capital').val()) - sum;
    if (currentSum > maxSum) {
      item.val(maxSum.toFixed(2))
    }
  })

  function saveCoOwner(changeOperations=false) {
    let coOwners = [];
    $('.co-owners-table').each(function() {
      let item = $(this);
      let coOwnerPk = item.data('co_owner_pk');
      let capital = item.find('.co-owner-capital input').val();
      if (capital === '')
        capital = 0
      let defaultShare = parseFloat(item.find('.co-owner-default-share input').val());
      coOwners.push({
        "pk": coOwnerPk,
        "capital": capital,
        "default_share": defaultShare
      })
    })

    $.post({
      url: '/api/edit-co-owners/',
      headers: {
        'X-CSRFTOKEN': csrfToken,
        'Content-Type': 'application/json'
      },
      data: JSON.stringify({
        'co_owners': coOwners,
        'change_prev_operations': changeOperations,
        'investment_account': $('#investment_account_pk').val()
      }),
      success: function () {
        window.location.reload()
      },
      errors: function (err) {
        alert(err.responseText)
      }
    })
  }
  $('#save-co-owners').on('click', function(){
    saveCoOwner()
  })

  $('#save-co-owners-with-shares').on('click', function(){
    saveCoOwner(true)
  })
  $('form').submit(function(e){
    e.preventDefault();
    $('.capital-field').focusout()
  });
})