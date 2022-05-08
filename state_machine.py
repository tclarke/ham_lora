import re

class InvalidTransition(Exception):
    pass


class State:
    def __init__(self, **kwargs):
        print("Enter state: " + self.__class__.__name__)
    
    def __call__(self, *args, **kwargs):
        raise InvalidTransition()


class InitialState(State):
    def __call__(self, mode=None, **kwargs):
        if mode == "beacon":
            return Bcn(**kwargs)
        elif mode == "sequence":
            return Seq(**kwargs)
        elif mode == "free":
            return Free(**kwargs)
        return self


class Bcn(State):
    def __call__(self, radio=None, short_press=[], **kwargs):
        if 1 in short_press:
            return BcnSend(**kwargs)
        data = radio.receive()
        if data is not None:
            return BcnPrnt(data=data, **kwargs)
        return self


class BcnPrnt(State):
    def __init__(self, data=None, ui=None, **kwrgs):
        ui.set_text(2, data)

    def __call__(self, short_press=[], **kwargs):
        if 1 in short_press:
            return BcnSend(**kwargs)
        return Bcn(**kwargs)


class BcnSend(State):
    MSG = 'BCN {mycall} {mygrid}'
    def __init__(self, msg_props={}, radio=None, **kwargs):
        m = BcnSend.MSG.format(**msg_props)
        radio.transmit(m)

    def __call__(self, **kwargs):
        return BcnWait(**kwargs)


class BcnWait(Bcn):
    def __init__(self, **kwargs):
        self._elapsed_time = 0

    def __call__(self, short_press=[], **kwargs):
        self._elapsed_time += 1
        if 1 in short_press:
            return Bcn(**kwargs)
        tmp = super().__call__(**kwargs)
        if tmp is self and self._elapsed_time >= 10:
            return BcnSend(**kwargs)
        return tmp


class Free(State):
    def __call__(self, radio=None, short_press=[], msgs=None, msg_idx=None, **kwargs):
        if 1 in short_press:
            return FreeSend(msgs=msgs, msg_idx=msg_idx, **kwargs)
        if 0 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] - 1) % len(msgs)
        if 2 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] + 1) % len(msgs)
        data = radio.receive()
        if data is not None:
            return FreePrnt(data=data, **kwargs)
        return self


class FreePrnt(State):
    def __init__(self, data=None, ui=None, **kwargs):
        ui.set_text(2, data)

    def __call__(self, short_press=[], **kwargs):
        if 1 in short_press:
            return FreeSend(**kwargs)
        return Free(**kwargs)


class FreeSend(State):
    def __init__(self, msg=None, radio=None, **kwargs):
        radio.transmit(msg)

    def __call__(self, **kwargs):
        return Free(**kwargs)


class Seq(State):
    def __call__(self, radio=None, short_press=[], msgs=None, msg_params=None, msg_idx=None, ui=None, **kwargs):
        m = [p.format(**msg_params) for p in msgs[msg_idx[0]:msg_idx[0]+3]]
        ui.set_all_text(m)
        if 1 in short_press:
            return SeqSend(msgs=msgs, msg_idx=msg_idx, **kwargs)
        if 0 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] - 1) % len(msgs)
        if 2 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] + 1) % len(msgs)
        data = radio.receive()
        if data is not None:
            return SeqParse(data=data, msgs=msgs, msg_idx=msg_idx, **kwargs)
        return self


class SeqParse(State):
    RE_BCN = 'BCN'
    RE_CALL = '[A-Z0-9]+\d[A-Z0-9]*[A-Z]'
    RE_GRID = '[A-Z][A-Z][0-9][0-9][A-Z]*'
    RE_RSSI = '[+-][1-9][0-9]*'

    RE_BCN_MSG = re.compile(f'^{RE_BCN}\s({RE_CALL})\s({RE_GRID})$')
    RE_CQ_MSG = re.compile(f'^CQ\s({RE_CALL})\s({RE_GRID})$')
    RE_SEQ1_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\s({RE_GRID})$')
    RE_SEQ2_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\s({RE_RSSI})$')
    RE_SEQ3_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\sR({RE_RSSI})$')
    RE_SEQ4_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\sRRR$')
    RE_SEQ5_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\s73$')

    def __init__(self, data=None, msgs=None, msg_idx=None, msg_params={}, ui=None, **kwargs):
        try:
            data = data.decode().upper()
        except UnicodeError:
            print("Invalid: "+data)
	    # start matching message types. Only try and parse the expected type
        parsed = None
        if msg_idx[0] == 0:
            p = SeqParse.RE_CQ_MSG.match(data)
            if p is not None:
                msg_params['theircall'], msg_params['theirgrid'] = p.groups()
                parsed = True
        elif msg_idx[0] == 1:
            p = SeqParse.RE_SEQ1_MSG.match(data)
            if p is not None:
                mycall, theircall, theirgrid = p.groups()
                if msg_params['mycall'] == mycall:
                    msg_params['theircall'], msg_params['theirgrid'] = theircall, theirgrid
                    parsed = True
        elif msg_idx[0] == 2:
            p = SeqParse.RE_SEQ2_MSG.match(data)
            if p is not None:
                mycall, theircall, myrssi = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    msg_params['myrssi'] = myrssi
                    parsed = True
        elif msg_idx[0] == 3:
            p = SeqParse.RE_SEQ3_MSG.match(data)
            if p is not None:
                mycall, theircall, myrssi = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    msg_params['myrssi'] = myrssi
                    parsed = True
        elif msg_idx[0] == 4:
            p = SeqParse.RE_SEQ4_MSG.match(data)
            if p is not None:
                mycall, theircall = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    # TODO: log
                    parsed = True
        elif msg_idx[0] == 5:
            p = SeqParse.RE_SEQ5_MSG.match(data)
            if p is not None:
                mycall, theircall = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    # TODO: log
                    del msg_params['theircall']
                    del msg_params['theirgrid']
                    del msg_params['theirrssi']
                    del msg_params['myrssi']
                    parsed = True
	
        if parsed:
            ui.set_text(2, data)
            msg_idx[0] = (msg_idx[0] + 1) % len(msgs)

    def __call__(self, short_press=[], **kwargs):
        if 1 in short_press:
            return SeqSend(**kwargs)
        return Seq(**kwargs)


class SeqSend(State):
    def __init__(self, radio=None, msgs=None, msg_idx=None, msg_params={}, **kwargs):
        if msgs is not None and msg_idx is not None:
            m = msgs[msg_idx[0]].format(**msg_params)
            radio.transmit(m)
            msg_idx[0] = (msg_idx[0] + 1) % len(msgs)
            if msg_idx[0] == 0:
                msg_params['theircall'] = '{theircall}'
                msg_params['theirgrid'] = '{theirgrid}'
                msg_params['theirrssi'] = '{rssi}'
                msg_params['myrssi'] = '{rssi}'

    def __call__(self, **kwargs):
        return Seq(**kwargs)


class StateMachine:
    def __init__(self, config):
        self.__state = InitialState()
        self.msg_idx=[0]
        self.msgs=[
            "CQ {mycall} {mygrid}",
            "{theircall} {mycall} {mygrid}",
            "{theircall} {mycall} {theirrssi}",
            "{theircall} {mycall} R{theirrssi}",
            "{theircall} {mycall} RRR",
            "{theircall} {mycall} 73",
        ]
        self.msg_params = {
            'mycall': config['callsign'],
            'mygrid': config['grid'],
            'theircall': '{theircall}',
            'theirgrid': '{theirgrid}',
            'theirrssi': '{rssi}',
            'myrssi': '{rssi}'
            }
    
    def __call__(self, **kwargs):
        kwargs.update(self.__dict__)
        self.__state = self.__state(**kwargs)
    
    def __str__(self):
        return f'StateMachine({self.__state.__class__.__name__})'