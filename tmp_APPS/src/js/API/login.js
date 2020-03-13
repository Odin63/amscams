var COOKIE_NAME = "APIa"          // Token Access
var USER_COOKIE_NAME = "APIu478"  // User info
var PAGE_MODIFIED = "AJIhgg"

// Test if already logged in 
function test_logged_in() {
   return readCookie(COOKIE_NAME); 
} 

function getTok() {
   return test_logged_in();
}

// Get User Info
function getUserInfo() {
   return readCookie(USER_COOKIE_NAME); 
}


// UI transformed after loggined (add delete buttons)
function add_login_stuff() {
   

    // Add buttons on the obs report page
    var delButton = '<a class="del col btn btn-danger btn-sm" title="Delete Detection"><i class="icon-delete"></i></a>';
    var confButton = '<a class="conf col btn btn-success btn-sm ml-1" title="Confirm Detection">Confirm </a>';
   
   
   // Add Confirm/Delete buttons on gallery
   if($('.lgi').length==0) {
 
      // Add buttons on the gallery
      $('.prevproc').each(function() {
            $('<div class="btn-toolbar lgi">\
               <div class="d-flex justify-content-around">\
                  '+delButton+'\
                  '+confButton+'\
               </div>\
            </div>').appendTo($(this))
      });
   }

   // Add Toolbos
   if($('#tool_box').length !=0) {
      // On Obs Page

      // DELETE
      if($('#tool_box .del').length==0) {
         $(delButton).html('<i class="icon-delete"></i> Delete').addClass('m-1 single').appendTo($('#tools'));
      }
      // CONF
      if($('#tool_box .conf').length==0) {
         $(confButton).html('<i class="icon-check"></i> Confirm').addClass('m-1 single').appendTo($('#tools'));
      } 
      // METEOR PICKER
      if($('#tool_box .reduc1').length==0) {
         $('<a class="reduc1 col btn btn-success btn-sm ml-1" title="Pick Meteor Position"><i class="icon-image"></i> Meteor Picker</a>').addClass('m-1 d-block w-100').appendTo($('#tools'));
      }

      // Show Tools
      $('#tool_box').removeClass('d-none');

      setup_single_delete_buttons();
      setup_single_conf_buttons();

   }

   // Show Details on Daily Report Page
   $('.lio').show();

   if(typeof setup_delete_buttons !== 'undefined') {
      setup_delete_buttons();
   }

   if(typeof setup_confirm_buttons !== 'undefined') {
      setup_confirm_buttons();
   } 


   // Setup Meteor Picker (Manual Reduce1)
   setup_manual_reduc1();

 

}

// Remove Login Stuff
function remove_login_stuff() {

   // Remove  Buttons
   $('.lgi').remove();
   $('.lio').hide();
   $('.prevproc').show();
   
   $('.toDel').removeClass('toDel');
   $('.toConf').removeClass('toConf');

   if (typeof hide_bottom_action !== 'undefined') {
      hide_bottom_action();
   }


   // Main Button on daily report
   $('#del_text').text('');
   $('#conf_text').text('');

   // Toolbox
   $('#tool_box').html('').addClass('d-none')


}


// Remove Login Cookie
function logout() {
   eraseCookie(COOKIE_NAME); 
   eraseCookie(USER_COOKIE_NAME); 
}


// Update UI based on logged or not 
function loggedin() {
   console.log("TEST LOGGED IN ")
   if(test_logged_in()!==null) {

      console.log("LOGGED IN")
      // Add buttons
      add_login_stuff();
      
      // Logout Button
      $("a#login").text('Logout').unbind('click').click(function() {
         logout();
         loggedin();
      });

      
   } 
   else {

      console.log("NOT LOGGED IN")

      $("a#login").text('Login');
      setup_login();
      remove_login_stuff();
   }        
}

// Add Login Modal
function add_login_modal() {
      // Add Login Modal
      if($('#login_modal').length==0) {
         $('<div id="login_modal" class="modal fade" tabindex="-1" role="dialog">\
            <div class="modal-dialog modal-dialog-centered" style="max-width:450px" role="document">\
            <div class="modal-content">\
            <div class="modal-header">\
            <h5 class="modal-title">Login to '+STATION+'</h5>\
            <button type="button" class="close" data-dismiss="modal" aria-label="Close">\
               <span aria-hidden="true">&times;</span>\
            </button>\
            </div>\
            <div class="modal-body p-4" >\
               <div class="d-flex justify-content-center form_container mb-4">\
                  <form style="width:250px">\
                     <input type="hidden" name="st" value="'+STATION+'"/>\
                     <div class="input-group mb-3">\
                        <input type="text" name="username" class="form-control input_user" value="" placeholder="username">\
                     </div>\
                     <div class="input-group mb-2">\
                        <input type="password" name="password" autocomplete="current-password" class="form-control input_pass" value="" placeholder="password">\
                     </div>\
                     <div class="d-flex justify-content-center mt-3 login_container">\
                        <button type="submit" name="button" id="subm_login" class="btn btn-primary" style="width: 100%;">Login</button>\
                     </div>\
                  </form>\
               </div>\
            </div></div></div></div>').appendTo('body');
      }
}


// Create Login Modal
function setup_login() {
 
   // Login
   $('#login').unbind('click').click(function(e){
      e.stopImmediatePropagation(); 
      $('#login_modal').on('shown.bs.modal', function () {
         $('input[name=username]').trigger('focus')
       })
      $('#login_modal').modal('show');
 

      $('#subm_login').click(function(e) {
            // So we can send the USR to the API
            var $t = $(this);
            
            var _data = {'function':'login', 'usr':$('input[name=username]').val(), 'pwd':$('input[name=password]').val(), 'st':stID};

            e.stopImmediatePropagation();

            loading_button($t);
            $.ajax({ 
               url:   API_URL ,
               data: _data, 
               format: 'json',
               success: function(data) { 
                  data = jQuery.parseJSON(data);  
                     
                  load_done_button($t);

                  if(typeof data.error !== 'undefined') {
                     // WRONG!
                     bootbox.alert({
                        message: data.error,
                        className: 'rubberBand animated error',
                        centerVertical: true 
                     });
                     logout();
                  } else {

                     $('#login_modal').modal('hide'); 
                     createCookie(COOKIE_NAME,data.token,2/24)
                     createCookie(USER_COOKIE_NAME,_data['usr']+'|'+_data['st'],2/24);
                     loggedin();    
                  } 
               }, 
               error:function() { 
                  load_done_button($t);
                  $('#login_modal').modal('hide');
                  bootbox.alert({
                     message: "Impossible to reach the API. Please, try again later.",
                     className: 'rubberBand animated error',
                     centerVertical: true 
                  });
                  logout();
                  loggedin();
               }
            });

            return false;
      })

      return false;
   }) 
}     