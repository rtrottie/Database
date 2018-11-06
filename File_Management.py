
def file_to_dict(acf, labels=None, start=0, end=None):
    '''
    Turn a file into a dictionary with labels corresponding to the keys.  if labels=None, use first line of the file
    :param acf: str
    :param labels: list
    :return: dict
    '''

    # Parse lines and setup labels if not provided
    lines = acf.split(b'\n')[start:end]
    if not labels:
        labels = lines[0].split()
        lines = lines[1:]
    # print(lines)
    # create output dictionary and initialize
    ACF = {}
    for label in labels:
        ACF[label] = []

    # Add each line to output dictionary, if and only if number of data points = number of labels
    for line in lines:
        data = line.split()
        if len(data) == len(labels):
            for j in range(len(data)):
                ACF[labels[j]].append(data[j])

    return ACF