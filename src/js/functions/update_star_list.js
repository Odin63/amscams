function update_cat_stars() {
    var cmd_data = {
        video_file:          main_vid,          // Defined on the page
        hd_stack_file:       hd_stack_file,     // Defined on the page
        cmd: 'show_cat_stars',                 
        cal_params_file:  $('#cal_param_selected').val(),   // The one selected 
        type: typeof type !== 'undefined' ? type : 'nopick', // 'nopick' is the default option
        points: ''
    }
 
    // Get user stars from array
    // cmd_data.points = user_stars.join("|")+"|";

    // Get Stars from canvas
    var canvas_stars = canvas.getObjects('circle');
    $.each(canvas_stars, function(i,v) {
        if (v.get('type') == "circle" && v.get('radius') == 5) {
            cmd_data.points= cmd_data.points + v.left.toString() + "," + v.top.toString() + "|";
         }
    }); 

    loading({text:'Updating star list...'});

    // Remove All objects from Canvas
    remove_objects();

    $.ajax({ 
        url:  "/pycgi/webUI.py",
        data: cmd_data,
        success: function(data) {
        
            var json_resp = $.parseJSON(data);
            var cat_stars = json_resp['close_stars'];     
           
            // Draw New Box
            canvas.add(
                new fabric.Rect({
                    fill: 'rgba(0,0,0,0)', 
                    strokeWidth: 1, 
                    stroke: 'rgba(230,230,230,.2)',  
                    left: json_resp['crop_box'][0] / 2, 
                    top: json_resp['crop_box'][1] / 2,
                    width: (json_resp['crop_box'][2] - json_resp['crop_box'][0]) / 2,
                    height: (json_resp['crop_box'][3] - json_resp['crop_box'][1]) / 2,
                    selectable: false
                 })
            );

            // Updating star table info 
            // Residual Error
            total_res_deg = (Math.round(total_res_deg * 100) / 100);
            total_res_px = (Math.round(total_res_px *100) / 100);
            $('#star_res_p').remove();
            $('<p id="star_res_p" class="mt-2"><b>Residual Error:</b> '+  total_res_deg + '&deg; / ' + total_res_px + 'px.</p>').insertBefore('#stars-tab table');

            // Add same text to image 
            res_desc = "Res. Star Error: " + total_res_deg + " degrees / " + total_res_px + " px \nTotal stars: " + cat_stars.length;
            canvas.add(new fabric.Text(res_desc , {
                fontFamily: 'Arial',
                fontSize: 12,
                left: 5 ,
                top: 5,
                fill: 'rgba(255,255,255,.75)',
                selectable: false
            }));


            var table_tbody_html = '';

            // Table - tbody (in #stars-tab) & draw on canvas
            
            $.each(cat_stars,function(i,v) {

                // Add to circle canvas
                canvas.add(
                    new fabric.Circle({
                        radius: 5, fill: 'rgba(0,0,0,0)', strokeWidth: 1, stroke: 'rgba(100,200,200,.5)', 
                        left: (v[13] - 11)/2, 
                        top: (v[14] - 11)/2,
                        selectable: false
                }));

                // Add "+" on canvas
                canvas.add(
                    new fabric.Text("+", {
                        fontFamily: 'Arial', 
                        fontSize: 12, 
                        left: ((v[7] - 11)/2)+4,   // +4 = shift text
                        top: ((v[8] - 11)/2) -4,    // -4 = shift text
                        fill:'rgba(255,0,0,.75)',
                        selectable: false
                }));

                // Add Star Name on canvas
                canvas.add(new fabric.Text(v[0], {
                        fontFamily: 'Arial', 
                        fontSize: 12, 
                        left: (v[11] - 11)/2+5,
                        top: (v[12] - 11)/2+8,
                        fill:'rgba(255,255,255,.45)',
                        selectable: false
                }));

                // Add Rectangle
                canvas.add(new fabric.Rect({
                    fill: 'rgba(0,0,0,0)', strokeWidth: 1, stroke: 'rgba(230,100,200,.5)', 
                    left:  (v[11] - 11)/2, 
                    top:(v[12] - 11)/2,
                    width: 10,
                    height: 10 ,
                    selectable: false
                 }));

                // Add the corresponding row
                // Name mag Cat RA/Dec  Res °   Res. Pixels
                table_tbody_html+= '<tr><td>'+v[0]+'</td><td>'+v[1]+'</td><td>'+v[2]+'/'+v[3]+'</td><td>'+v[6]+'</td><td>'+v[15]+'</td></tr>';

            });

            // Replace current table content
            $('#stars-tab tbody').html(table_tbody_html);

            // Open proper tab
            $('#stars-tab-l').click();
            
            loading_done();
 
        } 
    });
 
}



$(function () {

    $('#update_stars').click(function() {
        update_cat_stars();
    });

});
