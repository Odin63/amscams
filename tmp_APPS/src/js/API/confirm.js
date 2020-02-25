/********** UI ***********************************************************************/
function setup_confirm_buttons() {
   $('.conf').each(function() {
      var $t = $(this); 
      $t.unbind('click').click(function() {   
         $t.closest('.prevproc').removeClass('toDel');
         if($t.closest('.prevproc').hasClass('toConf')) {
            $t.addClass('on');
            $t.closest('.prevproc').removeClass('toConf');
         } else {
            $t.removeClass('on');
            $t.closest('.prevproc').addClass('toConf');
         }
         check_bottom_action();
      });
   })
}