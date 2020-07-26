$(document).ready(function() {
  const csrfToken = $('meta[name="csrf-token"]').prop('content')
  let editShare = $('.edit-share');

  // Редактирование доли у операции
  editShare.on('click', function(){
    let item = $(this);
    if (item.has('input').length > 0)
      return
    let shareValue = item.data('value')

    item.html(item.html() + `<input type="number" class="form-control w-50" value="${shareValue}">`)
    item.find('input').focus()
  })

  // Отправляем новое значение доли на сервер
  editShare.focusout('input', function(){
    let item = $(this);
    const sharePk = item.data('pk');
    let shareValue = parseInt(item.find('input').val());
    let investorName = item.data('investor');

    $.ajax({
      method: 'patch',
      url: `/api/share/${sharePk}/`,
      headers: {
        'X-CSRFTOKEN': csrfToken,
        'Content-Type': 'application/json'
      },
      data: JSON.stringify({
        'value': shareValue
      }),
      success: function(){
        item.find('input').remove();
        item.html(`&rfisht; ${investorName}: ${shareValue}`)
        item.data('value', shareValue)
      },
      error: function(err){
        alert(err.responseText)
        // alert(JSON.stringify(err))
      }
    });
  })
})