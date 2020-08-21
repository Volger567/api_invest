$(document).ready(function() {
  let timer;
  const maxCapital = $('#total-capital').val();
  const csrfToken = $('meta[name="csrf-token"]').prop('content')
  const investmentAccountPk = $('#investment_account_pk').val();

  // При написании символа в строку поиска инвесторов
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
        url: `/api/investors/?search=${item.val()}`,
        dataType: 'json',
        headers : {
          'X-CSRFTOKEN': csrfToken
        },
        success: function(data) {
          investorsElement.text('')
          data.forEach(function(user){
            investorsElement.append(`<button class="btn btn-primary m-1 add-co-owner-btn" data-id="${user.id}">${user.username}</button>`)
          })
        },
      })
    }, 500)
  })

  // Добавить совладельца
  $(document).on('click', '.add-co-owner-btn', function() {
    let investorId = $(this).data('id')
    $.post({
      url: '/api/co-owners/',
      headers: {
        'X-CSRFTOKEN': csrfToken
      },
      data: {
        'investor': investorId,
        'investment_account': investmentAccountPk,
      },
      success: function () {
        window.location.reload()
      },
      error: function (err) {
        alert(err.responseText)
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
    let capital = {}
    $('.co-owner-capital').each(function(){
      let el = $(this).children("input");
      const ID = el.data("id");
      if (!(ID in capital))
        capital[ID] = {}
      capital[ID]["value"] = parseFloat(el.val());
    })

    $('.co-owner-default-share').each(function(){
      let el = $(this).children("input");
      const ID = el.data("id");
      capital[ID]["default_share"] = parseFloat(el.val());
    })

    $.ajax({
      method: "PATCH",
      url: "/api/capital/multiple_updates/",
      headers: {
        "X-CSRFTOKEN": csrfToken,
        "Content-Type": "application/json"
      },
      data: JSON.stringify(capital),
      success: function () {
        window.location.reload()
      },
      error: function (err) {
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