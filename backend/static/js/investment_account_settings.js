$(document).ready(function() {
  let timer;
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
      dataType: 'json',
      success: function (data) {
        window.location.reload()
      }
    })
  })
})