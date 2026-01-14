import aiofiles

promoMap = None
filename = 'promo.txt'

def set_global_promo_map(value):
    global promoMap
    promoMap = value

async def readFileToMap():
    map_result = {}
    line_number = 0

    async with aiofiles.open(filename, mode='r') as file:
        async for line in file:
            map_result[line_number] = line.strip()
            line_number += 1

    print(len(map_result))
    return map_result

def write_map_to_file():
    with open(filename, 'w') as file:
        for key, value in promoMap.items():
            file.write(f'{value}\n')   
    print(len(promoMap))

def getPromo():    
    sizeMap = len(promoMap)
    element = promoMap[sizeMap-1]    
    promoMap.pop(sizeMap-1)
    write_map_to_file()
    return element    
    