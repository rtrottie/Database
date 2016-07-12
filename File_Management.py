
def read_ACF(acf):
    '''

    :type acf: file
    :return:
    '''

    labels = ['#', 'x', 'y', 'z', 'charge', 'min_dist', 'volume']
    ACF = {}
    for label in labels:
        ACF[label] = []
    i = -1
    lines = acf.read().split('\n')
    for line in lines:
        i += 1
        if i > 1:
            data = line.split()
            for j in range(len(data)):
                ACF[labels[j]].append(data[j])

    return ACF