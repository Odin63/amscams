function setup_delete_frame() {
    // Delete Frame
    $('.delete_frame').click(function() {
        var  $row = $(this).closest('tr');
        var  id = $row.attr('id');

        // Get the frame ID
        // the id should be fr_{ID}
        var d = id.split('_');
  
        $.ajax({ 
            url:  "/pycgi/webUI.py?cmd=del_frame&meteor_json_file=" + meteor_json_file + "&fn=" + d[1],
            success: function(response) {
                $row.fadeOut(150, function() {$row.remove();})
            } 
        });
    
    });

}


function delete_frame_from_crop_modal(fn) {

    var  $row = $('tr#fr_'+fn); 
    loading({"text":"Deleting frame #"+fn,"overlay":true});
    $row.css('opacity',0.5).find('a').hide();

    $.ajax({ 
        url:  "/pycgi/webUI.py?cmd=del_frame&meteor_json_file=" + meteor_json_file + "&fn=" + fn,
        success: function(response) { 
                var tr_fn = false;
                var tr_id = fn; 
                update_reduction_only(function() {
                    $('.modal-backdrop').remove();
                    $('#select_meteor_modal').modal('hide').remove();
    
                    // Try to find first next frame
                    for(var i=fn+1;i<fn+20;i++) {
                        if($('tr#fr_'+i).length!=0) {
                            tr_id = i;
                            tr_fn = true;
                        }
                    }
    
                    if(!tr_fn) {
                        for(var i=fn-1;i<fn-20;i--) {
                            if($('tr#fr_'+i).length!=0) {
                                tr_id = i;
                                tr_fn = true;
                            }
                        }
                    }

                    if(tr_fn) {
                        $('tr#fr_'+tr_id+' .select_meteor').click(); 
                    }

 
    
                });
               
                
             
        } 
    });



}
 