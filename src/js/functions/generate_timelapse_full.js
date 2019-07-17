function add_timelapse_full_modal() {

    // Init date picker with current date
    var utcMoment = moment.utc();
    var curD = utcMoment.format('YYYY/MM/DD');

    // Get the Cam IDs for the select
    var cam_ids = $('input[name=cam_ids]').val();
    cam_ids = cam_ids.split('|');

    var cam_select = "<select name='cam' class='form-control'>";
    $.each(cam_ids,function(i,v){
        if($.trim(v)!=='') {
            cam_select = cam_select + "<option value='"+v+"'>" + v + "</option>";
        }
    });
    cam_select = cam_select + "</select>";


    $('#full_timelapse_modal').remove(); 
    $('<div id="full_timelapse_modal" class="modal" tabindex="-1" role="dialog"> \
        <div class="modal-dialog modal-dialog-centered modal-lg" role="document"> \
            <div class="modal-content"> \
            <div class="modal-header"> \
                <h5 class="modal-title">Generate Timelapse</h5> \
                <button type="button" class="close" data-dismiss="modal" aria-label="Close"> \
                <span aria-hidden="true">&times;</span> \
                </button> \
            </div> \
            <div class="modal-body"> \
                <form id="timelapse_full_form"> \
                    <div class="row"> \
                        <div class="col-sm-6"> \
                            <div class="form-group row mb-1"> \
                                <label class="col-sm-4 col-form-label"><b>Date</b></label> \
                                <div class="col-sm-8"> \
                                <div class="input-group date datepicker" data-display-format="YYYY/MM/DD"> \
                                    <input value="'+curD+'" type="text" class="form-control"> \
                                </div> \
                            </div> \
                            <div class="form-group row mb-1"> \
                                <label class="col-sm-4 col-form-label"><b>Camera</b></label> \
                                <div class="col-sm-8" id="cam_select_h"></div> \
                            </div> \ 
                        </div> \
                        <div class="col-sm-6"> \
                            <div class="form-group row mb-1"> \
                                <label for="fps" class="col-sm-4 col-form-label"><b>FPS</b></label> \
                                <div class="col-sm-8"> \
                                    <select name="fps" class="form-control"> \
                                        <option value="1">1 fps</option> \
                                        <option value="5">5 fps</option> \
                                        <option value="10">10 fps</option> \
                                        <option value="15">15 fps</option> \
                                        <option value="23.976">23.976 fps</option> \
                                        <option value="24">24 fps</option> \
                                        <option value="25">25 fps</option> \
                                        <option value="29.97" >29.97 fps</option> \
                                        <option value="30" selected>30 fps</option> \
                                        <option value="50">50 fps</option> \
                                        <option value="59.94">59.94 fps</option> \
                                        <option value="60">60 fps</option> \
                                    </select> \
                                </div> \
                            </div> \
                            <div class="form-group row mb-1"> \
                                <label for="dim" class="col-sm-4 col-form-label"><b>Dimension</b></label> \
                                <div class="col-sm-8"> \
                                    <select name="dim" class="form-control"> \
                                        <option value="1920:1080">1920x1080</option> \
                                        <option value="1280:720" selected>1280x720</option> \
                                        <option value="640:320">640x320</option> \
                                    </select> \
                                </div> \
                            </div> \
                            <div class="form-group row mb-1"> \
                                <label for="text_pos" class="col-sm-4 col-form-label"><b>Info pos.</b></label> \
                                <div class="col-sm-8"> \
                                    <select name="text_pos" class="form-control"> \
                                        <option value="tr">Top right</option> \
                                        <option value="tl" >Top Left</option> \
                                        <option value="br" >Bottom Right</option> \
                                        <option value="bl" selected>Bottom Left</option> \
                                    </select> \
                                </div> \
                            </div> \
                            <div class="form-group row mb-1"> \
                                <label for="wat_pos" class="col-sm-4 col-form-label"><b>Logo pos.</b></label> \
                                <div class="col-sm-8"> \
                                    <select name="wat_pos" class="form-control"> \
                                        <option value="tr" selected>Top right</option> \
                                        <option value="tl" >Top Left</option> \
                                        <option value="br" >Bottom Right</option> \
                                        <option value="bl" >Bottom Left</option> \
                                    </select> \
                                </div> \
                            </div> \
                        </div> \
                        <div class="col-sm-12"> \
                            <div class="form-group">\
                                <label for="extra_text" class="col-form-label"><b>Extra info</b></label> \
                                <input type="text" name="extra_text" class="form-control" value=""/> \
                            </div>\
                        </div>\
                </form> \
            </div> \
            </div> \
            <div class="modal-footer"> \
                <button type="button" id="generate_timelapse" class="btn btn-primary">Generate</button> \
                <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button> \
            </div> \
        </div> \
        </div>').appendTo('body').modal('show');

    // Cam selecteor
    $('#cam_select_h').html(cam_select);

    //Start datepicker
    load_date_pickers();

    // How many frames 
    hmf = $('img.lz').not('.process').length;
    $('#tot_f').val(hmf);

    // Cam ID 
    $('#tl_cam_id').val($('#cam_id').val());
    console.log('CAM ID VAL ', $('#cam_id').val());

    // Date
    $('#tl_date').val($('input[name=cur_date]').val());

    // Init duration
    $('#tld').val(parseFloat($('#tot_f').val()/parseFloat($('select[name=fps]').val())).toFixed(2) + ' seconds');

    // Update duration 
    $('select[name=fps]').unbind('change').bind('change',function() {
        $('#tld').val(parseFloat($('#tot_f').val()/parseFloat($(this).val())).toFixed(2) + ' seconds');
    });

    // Generate
    $('#generate_timelapse').click(function() { 
        var cmd_data = getFormData($("#timelapse_full_form"));
        cmd_data.cmd = "generate_timelapse";

 
        $('#full_timelapse_modal').modal('hide');
        loading({text: "Creating Video", overlay: true});
        
        $.ajax({ 
            url:  "/pycgi/webUI.py",
            data: cmd_data,
            success: function(data) {
                var json_resp = $.parseJSON(data); 
                bootbox.alert({
	                message: json_resp.msg,
	                className: 'rubberBand animated',
	                centerVertical: true
                });
                loading_done();
            }, 
            error:function(err) {
                bootbox.alert({
	                message: "The process returned an error - please try again later",
	                className: 'rubberBand animated error',
	                centerVertical: true
                });
                
                loading_done();
            }
        });
    });
}

$(function() {
    $('#create_timelapse').click(function() {
        add_timelapse_full_modal();    
    });
})