function img = readRaw10(fn_folder,fn_name,output_folder,h,w)
    input_file = fullfile(fn_folder,fn_name);
    [~,fN,~] = fileparts(fn_name);
    output_file = fullfile([output_folder,'\',fN,'_16.raw']);
    % python3 unpack_mipi_raw10.py -i <raw file name> -o <output PNG file name> -m 1 -x 2560 -y 2560 -s 3200
    [a,b] = system(['python3 unpack_mipi_raw10.py -i ' input_file ' -o ' output_file ' -x 4032 -y 3024 -s 5040']);
    if(a ~= 0)
        ['Error in executing command:',b];
    end
    fid = fopen(output_file,'r');
    img = fread(fid,[w,h],'uint16');
    img = single(img');
    figure(1)
    clf
    imagesc(img)
    axis equal
    title(['Mean Signal = ',num2str(mean2(img(:)))])
    fclose(fid);
    [~,fN,~] = fileparts(fn_name);
    saveas(1,fullfile(output_folder,[fN,'.png']))
end