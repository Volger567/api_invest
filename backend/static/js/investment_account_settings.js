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
            let username = user['username']
            investorsElement.append(`<button class="btn btn-primary m-1 add-co-owner-btn">${username}</button>`)
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

  // $('.capital-field').change(function() {
  //   let item = $(this);
  //   let currentSum = parseFloat(item.val());
  //   let sum = 0;
  //   $('.capital-field').not(item).each(function() {
  //     sum += parseFloat($(this).val())
  //   })
  //   let totalSum = sum + currentSum;
  //   const maxSum = parseFloat($('#total-capital').val()) - sum;
  //   if (currentSum > maxSum) {
  //     item.val(maxSum.toFixed(2))
  //     totalSum = totalSum - currentSum + maxSum;
  //     currentSum = maxSum;
  //   }
  //   $('.creator-capital-field').val((maxCapital - totalSum).toFixed(2))
  //   recountIncomeAndLeftCapital()
  // })
  //
  // $('.share-field').change(recountIncomeAndLeftCapital)
  //
  // function recountIncomeAndLeftCapital() {
  //   const totalIncome = parseFloat($('#total-income').val());
  //   const coOwnersTables = $('.co-owners-table');
  //   const coOwnersShare = $('.co-owner-share')
  //   let totalShare = 0
  //   coOwnersShare.each(function() {
  //     let share = parseFloat($(this).children('input').val());
  //     if (!isNaN(share))
  //       totalShare += share
  //   })
  //
  //   coOwnersTables.each(function() {
  //     const capital = parseFloat($(this).find('tbody tr:first-child th:nth-child(1) input').val());
  //     const share = parseFloat($(this).find('tbody tr:first-child th:nth-child(2) input').val());
  //     let income = share/totalShare*totalIncome
  //     if (isNaN(income))
  //       income = 0
  //     else
  //       income = parseFloat(income.toFixed(2))
  //     $(this).find('tbody tr:first-child th:nth-child(3)').text(income)
  //     $(this).find('tbody tr:first-child th:nth-child(4)').text((capital + income).toFixed(2))
  //   })
  // }

  $('form').submit(function(e){
    e.preventDefault();
    $('.capital-field').focusout()
  });
  recountIncomeAndLeftCapital()
})