from aqt import mw
from aqt.qt import QAction
from .vocab_miner import VocabMinerDialog

def open_vocab_miner():
    dialog = VocabMinerDialog(mw)
    dialog.exec()

action = QAction("Vocab Miner", mw)
action.triggered.connect(open_vocab_miner)
mw.form.menuTools.addAction(action)
