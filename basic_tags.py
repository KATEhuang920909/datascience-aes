import csv
import nltk
import sys
import os
import os.path
import time
import syllables
from nltk.corpus import wordnet
import enchant
import argparse
import random
import re
import collections
import itertools
import multiprocessing
import cPickle

from pos_dict import pos_dict
pos_cnt_all = collections.Counter()

syl = syllables.cmusyllables()
syl.Load()

enchantDict = enchant.Dict("en_US")

PUNCTUATION = set(('.', ',', '"', "'", '`', ':', ';', '!', '~', '-', '=', '+', '?',
    '(', ')', '[', ']', '{', '}', '<', '>', '*', '^', '%', '_', '|', "@", "`",
    '\xe2', '\x80', '\x98', '\xe2', '\x80', '\x99', '\xe2', '\x80', '\x9c', '\xe2', '\x80', '\x9d'
    ))

proper_quote_re = re.compile(ur'''[\.,\?\!]["\u201c\u201d]''')
bad_quote_re = re.compile(ur'''["\u201c\u201d][\.,\?\!]''')

CONTRACTIONS = set(("'s", "wo", "n't", "'re", "'m", "'ve", "'ll", "isn"))
websites = ("myspace", "facebook", "youtube", "e-mail", "google", "hand-eye", "eye-hand", "webcam", "microsoft", "caps1", "yahoo", "wikipedia")
SPECIAL_WORDS = set(("e-mail", "hand-eye", "eye-hand", "webcam", "webcams", "skype", "powerpoint", "english", "america", "american", "netbook"))
SPECIAL_WORDS.update(websites)
SPECIAL_WORDS.update(x + ".com" for x in websites)
SPECIAL_WORDS.update("www." + x + ".com" for x in websites)

NER_re = re.compile(r"""(?:organization|caps|date|percent|person|money|location|num|month|time)\d+$""")
NERs = ["person", "organization", "location", "date", "time", "money", "percent", "caps", "num", "month"]



keys = ["id", "set", "essay", "rate1", "rate2", "grade",
    "num_chars", "num_sents", "num_words", "num_syl", "sentance_length", "num_correctly_spelled", "fk_grade_level",
    "starts_with_dear", "distinct_words", "end_with_preposition",
    "num_nouns", "num_verbs", "num_adjectives", "num_adverbs", "num_superlatives",
    "has_comma", "has_semicolon", "has_questionmark", "has_exclamation", "num_quotes", "proper_quote_punc"]
keys.extend("ner_%s" % x for x in NERs)
keys.extend("pos_%s" % x for x in sorted(pos_dict.keys()))

def processRow(row):
    result = dict(zip(
        ["id", "set", "essay", "rate1", "rate2", "grade",],
        row))
    sys.stdout.write("\r %s#%s" % (row[1], row[0]))
    sys.stdout.flush()

    text_asis = row[2].decode('mac-roman')
    text = row[2].strip().decode('mac-roman').lower()

    result["num_chars"] = len(text)

    sents = nltk.sent_tokenize(text)
    num_sents = len(sents)
    result["num_sents"] = num_sents

    words_in_sentances = [nltk.word_tokenize(sentance) for sentance in sents]
    words = []
    for sent in words_in_sentances:
        for word in sent:
            if word not in PUNCTUATION and not all(char in PUNCTUATION for char in word):
                words.append(word)
    num_words = len(words)
    result["num_words"] = num_words

    result["sentance_length"] = num_words / float(num_sents)


    num_correctly_spelled = 0
    for word in words:
        try:
            if enchantDict.check(word) or NER_re.match(word) or word in CONTRACTIONS or word in SPECIAL_WORDS:
                num_correctly_spelled += 1
            # else:
            #     print word.encode('utf-8')
        except enchant.errors.Error:
            print "can't spell check", word
    result["num_correctly_spelled"] = num_correctly_spelled


    num_syl = 0
    for word in words:
        num_syl += syl.SyllableCount(word)
    result["num_syl"] = num_syl

    fk_grade_level = (0.39 * (num_words / num_sents)) \
        + (11.8 * (num_syl / num_words)) - 15.59
    result["fk_grade_level"] = fk_grade_level

    if words[0] == 'dear':
        result["starts_with_dear"] = 1
    else:
        result["starts_with_dear"] = 0

    result["distinct_words"] = len(set(words))

    #Part of Speech tagging
    tagged_sentences = [nltk.pos_tag(sent) for sent in words_in_sentances]

    for pos in pos_dict.keys()
        result["pos_%s" % pos] = 0
    for word, pos in itertools.chain(*tagged_sentences):
        if pos in pos_dict.keys():
            result["pos_%s" % pos] += 1
        pos_cnt_all[pos] += 1

    #flag ending in a preposition
    result["end_with_preposition"] = 0
    for sent in tagged_sentences:
        try:
            if sent[-2][1] == "IN":
                result["end_with_preposition"] += 1
        except:
            pass

    #these lines are too clever
    #try to sum up the counts in the result table for each of these parts of speech to get combos
    result["num_nouns"] = sum(result.get("pos_%s" % key, 0) for key in ("NN", "NNP", "NNS"))
    result["num_verbs"] = sum(result.get("pos_%s" % key, 0) for key in ("VB", "VBD", "VBG", "VBN", "VBP", "VBZ"))
    result["num_adjectives"] = sum(result.get("pos_%s" % key, 0) for key in ("JJ", "JJR", "JJS"))
    result["num_adverbs"] = sum(result.get("pos_%s" % key, 0) for key in ("RB", "RBR", "RBS"))
    result["num_superlatives"] = sum(result.get("pos_%s" % key, 0) for key in ("JJS", "RBS"))


    n_proper_quotes = len(proper_quote_re.findall(text_asis))
    n_bad_quotes = len(bad_quote_re.findall(text_asis))
    if n_proper_quotes > n_bad_quotes:
        result["proper_quote_punc"] = 1
    elif n_proper_quotes < n_bad_quotes:
        result["proper_quote_punc"] = -1
    else:
        result["proper_quote_punc"] = 0
    result["has_comma"] = 1 if "," in text else 0
    result["has_semicolon"] = 1 if ";" in text else 0
    result["has_questionmark"] = 1 if "?" in text else 0
    result["has_exclamation"] = 1 if "!" in text else 0
    result["num_quotes"] = len([char for char in text_asis if char in u'"\u201c\u201d'])

    #frequencies of NER
    for ner in NERs:
        matches = re.findall(r"@%s\d+\b" % ner.upper(), text_asis)
        result["ner_%s" % ner] = len(matches)


    # print text
    # print sents
    # print words_in_sentances
    # print words
    # print tagged_sentences

    return result



class Worker(multiprocessing.Process):
    """
    Process the input queue of CSV rows with processRow(row), putting
    the output on a separate output queue. When it encounters None it knows the
    queue is depleted and it should quit, but first it puts a None on the output
    so the output processor knows it's done.
    """
    def __init__(self, input_queue, result_queue):
        multiprocessing.Process.__init__(self)
        self.input_queue = input_queue
        self.result_queue = result_queue

    def run(self):
        while True:
            row = self.input_queue.get()
            if row is None:
                self.result_queue.put(None)
                print pos_cnt_all
                break
            else:
                result = processRow(row)
                self.result_queue.put(result)

class OutputWorker(multiprocessing.Process):
    """
    Processes the output queue and writes the dictionaries to a CSV. Looks for
    n_workers occurrences of None on the queue to indicate that it's done and
    should quit.
    """
    def __init__(self, result_queue, out_csv, n_workers, outfile):
        multiprocessing.Process.__init__(self)
        self.result_queue = result_queue
        self.out_csv = out_csv
        self.n_done = 0
        self.n_workers = n_workers
        self.allrows = []
        self.outfile = outfile

    def run(self):
        while True:
            result = self.result_queue.get()
            if result is None:
                self.n_done += 1
                if self.n_done == self.n_workers:
                    self.outfile.flush()
                    self.outfile.close()
                    cPickle.dump(self.allrows, open("something.pickle", "wb"), cPickle.HIGHEST_PROTOCOL)
                    print #clear the output line since it's time to quit
                    break
            else:
                self.out_csv.writerow(result)
                self.allrows.append(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--max', '-n', type=int, help="Maximum number of lines before bailing")
    parser.add_argument('--sample', '-s', type=float, help="Sample S*100% of the rows")
    parser.add_argument('inputFilename')
    args = parser.parse_args()
    maxRows = args.max
    sample = args.sample
    inputFilename = args.inputFilename

    input = csv.reader(open(inputFilename, "rU"), delimiter="\t")
    header = input.next()

    outputFilename = os.path.splitext(os.path.basename(inputFilename))[0] + "_tagged.csv"
    outfile = open(outputFilename, "w")
    output = csv.DictWriter(outfile, keys)
    output.writerow(dict(zip(keys, keys)))
    outfile.flush()

    input_queue = multiprocessing.Queue(20)
    result_queue = multiprocessing.Queue()
    n_workers = multiprocessing.cpu_count()
    workers = []
    for i in range(n_workers):
        worker = Worker(input_queue, result_queue)
        worker.start()
        workers.append(worker)

    output_worker = OutputWorker(result_queue, output, n_workers, outfile)
    output_worker.start()
    workers.append(output_worker)

    for i, row in enumerate(input):
        if not (sample and random.random() > sample):
            input_queue.put(row)
        if maxRows and i >= maxRows:
            break

    for i in range(n_workers):
        input_queue.put(None)
    # while not input_queue.empty() or not result_queue.empty():
    #     time.sleep(5)

    # for worker in workers:
    #     worker.terminate()


if __name__ == "__main__":
    main()
