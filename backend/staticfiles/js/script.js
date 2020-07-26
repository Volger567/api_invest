$(document).ready(function(){
  // Делаем активной ссылку в меню
  $(`a[href="${location.pathname}"]:first-child`).parent().addClass('active');
})