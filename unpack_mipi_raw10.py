import argparse
import numpy as np
import imageio
import math

def unpack_mipi_raw10(input_raw, width, stride, height, header, verbose):
    ret = -1
    try:
        temp_width = 0
        raw = input_raw[header::]
        if stride <= 0:
            if raw.size*4/5 < width*height:
                raise ValueError('file size does not match width * height')
            temp_width = width*5/4
            raw = raw[0:int(width*height*5/4):]
        else:
            if raw.size < stride*height:
                raise ValueError('MIPI RAW10 file size should be multiple of stride')
            if stride * 4 / 5 < width:
                raise ValueError('stride and width setting do not match')
            raw = raw[0:stride*height:]
            raw = raw.reshape((height, stride))
            temp_width = math.floor(stride / 5) * 5
            raw = raw[::,:temp_width:]
            raw = raw.flatten()

        raw = raw.astype(np.uint32)
        raw1 = raw[::5]
        raw2 = raw[1::5]
        raw3 = raw[2::5]
        raw4 = raw[3::5]
        low_bits = raw[4::5]
        raw1 = raw1 * 4 + np.bitwise_and(low_bits, np.ones(low_bits.shape, dtype=np.uint32)*3)
        raw2 = raw2 * 4 + np.bitwise_and(np.right_shift(low_bits, np.ones(low_bits.shape, dtype=np.uint32)*2), np.ones(low_bits.shape, dtype=np.uint32)*3)
        raw3 = raw3 * 4 + np.bitwise_and(np.right_shift(low_bits, np.ones(low_bits.shape, dtype=np.uint32)*4), np.ones(low_bits.shape, dtype=np.uint32)*3)
        raw4 = raw4 * 4 + np.bitwise_and(np.right_shift(low_bits, np.ones(low_bits.shape, dtype=np.uint32)*6), np.ones(low_bits.shape, dtype=np.uint32)*3)

        upack_raw = np.zeros((int(raw.size*4/5), ), dtype=np.uint32)
        upack_raw[::4] = raw1
        upack_raw[1::4] = raw2
        upack_raw[2::4] = raw3
        upack_raw[3::4] = raw4

        upack_raw = np.where(upack_raw > 1023, 1023, upack_raw)
        upack_raw = upack_raw.astype(np.uint16)
        if( temp_width*4/5 != width ):
            upack_raw = upack_raw.reshape((height, int(temp_width*4/5)))
            upack_raw = upack_raw[::,:width:]
            upack_raw = upack_raw.flatten()

        ret = upack_raw.reshape((height, width))

    except OSError as err:
        print("OS error: {0}".format(err))
    except ValueError as err:
        print("Value error: {0}".format(err))
    return ret

#############################################################################################################

#############################################################################################################
#					unpack MIPI RAW10 packed RAW and save as unpacked RAW or PNG file						#
#############################################################################################################

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='unpack MIPI RAW10 RAW')

    parser.add_argument('-v', action='store', dest='verbose', default = 0, type=int, help='select to pring debug information')
    parser.add_argument('-i', action='store', dest='input_raw', default = [], type=str, help='file name of MIPI RAW10 RAW file to be unpacked', required = True)
    parser.add_argument('-o', action='store', dest='output_file', default = [], type=str, help='file name of unpacked RAW data', required = True)
    parser.add_argument('-m', action='store', dest='image_file', default = 0, type=int, help='select output format: 1: image file defined by extension of output_file, else: 16bit RAW')
    parser.add_argument('-x', action='store', dest='width', default = 2328, type=int, help='width of image')
    parser.add_argument('-s', action='store', dest='stride', default = 2912, type=int, help='number of bytes of row stride')
    parser.add_argument('-y', action='store', dest='height', default = 1748, type=int, help='height of image')
    parser.add_argument('-d', action='store', dest='header', default = 0, type=int, help='header size of image in byte')

    version = 0.1
    print("The version number is %.2f"%version)
    results = parser.parse_args()

    raw = np.fromfile(results.input_raw, dtype=np.uint8)
    upack_raw = unpack_mipi_raw10(raw, results.width, results.stride, results.height, results.header, results.verbose)
    if( results.image_file == 1):				# save RAW as an image file
        upack_raw = upack_raw * 64		# 10bit -> 16bit to make it visible
        imageio.imwrite(results.output_file, upack_raw)
    else:
        upack_raw.tofile(results.output_file)
