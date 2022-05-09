import re
import time

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
    def __init__(self, ui=None, radio=None, **kwargs):
        super().__init__(**kwargs)
        ui.set_rx(True)
        ui.set_mode_beacon()
        ui.set_select(-1)
        radio.listen()
        
    def __call__(self, ui=None, bkn_count=None, radio=None, short_press=[], **kwargs):
        ui.draw_time()
        ui.set_tx(False)
        if 0 in short_press:
            bkn_count[0] = 0
            ui.set_text(0, "")
            ui.set_text(1, "")
        if 1 in short_press:
            return BcnSend(ui=ui, radio=radio, **kwargs)
        data = radio.receive(0.1)
        if data is not None:
            return BcnPrnt(ui=ui, bkn_count=bkn_count, data=data, **kwargs)
        return self


class BcnPrnt(State):
    def __init__(self, bkn_count=None, data=None, ui=None, **kwargs):
        super().__init__(**kwargs)
        if type(data) is bytearray:
            data = data.decode()
        bkn_count[0] += 1
        ui.set_text(0, str(bkn_count[0]))
        ui.set_text(1, data)
        print(f'Received beacon: {data}')

    def __call__(self, short_press=[], **kwargs):
        if 1 in short_press:
            return BcnSend(**kwargs)
        return Bcn(**kwargs)


class BcnSend(State):
    MSG = 'BCN {mycall} {mygrid}'
    def __init__(self, msg_params={}, radio=None, ui=None, config=None, **kwargs):
        super().__init__(**kwargs)
        m = BcnSend.MSG.format(**msg_params)
        ui.set_tx(True)
        print(f'BcnSend: {m}')
        for i in range(config.get('ping_length', 1)):
            radio.transmit(m)
            time.sleep(0.25)

    def __call__(self, **kwargs):
        return BcnWait(**kwargs)


class BcnWait(Bcn):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._start_time = time.time()

    def __call__(self, config=None, short_press=[], **kwargs):
        end_time = time.time()
        if 1 in short_press:
            return Bcn(**kwargs)
        tmp = super().__call__(config=config, **kwargs)
        if tmp is self and (end_time - self._start_time) >= config['beacon_time']:
            return BcnSend(config=config, **kwargs)
        return tmp


class Free(State):
    def __call__(self, radio=None, ui=None, short_press=[], msgs=None, msg_idx=None, **kwargs):
        if 1 in short_press:
            return FreeSend(msgs=msgs, msg_idx=msg_idx, **kwargs)
        if 0 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] - 1) % len(msgs)
        if 2 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] + 1) % len(msgs)
        ui.set_rx(True)
        ui.set_tx(False)
        ui.set_mode_free()
        data = radio.receive()
        if data is not None:
            return FreePrnt(data=data, **kwargs)
        return self


class FreePrnt(State):
    def __init__(self, data=None, ui=None, **kwargs):
        super().__init__(**kwargs)
        ui.set_text(2, data)

    def __call__(self, short_press=[], **kwargs):
        if 1 in short_press:
            return FreeSend(**kwargs)
        return Free(**kwargs)


class FreeSend(State):
    def __init__(self, ui=None, msg=None, radio=None, **kwargs):
        super().__init__(**kwargs)
        ui.set_tx(True)
        radio.transmit(msg)

    def __call__(self, **kwargs):
        return Free(**kwargs)


class Seq(State):
    def __init__(self, radio=None, ui=None, msgs=None, msg_params=None, msg_idx=None, **kwargs):
        super().__init__(**kwargs)
        ui.set_rx(True)
        ui.set_tx(False)
        ui.set_mode_sequence()
        Seq.show_msgs(ui, msgs, msg_params, msg_idx)
        radio.listen()
    
    @staticmethod
    def show_msgs(ui=None, msgs=None, msg_params=None, msg_idx=None):
        m = [p.format(**msg_params) for p in msgs[msg_idx[0]:msg_idx[0]+2]]
        ui.set_all_text([
            msgs[msg_idx[0]].format(**msg_params),
            msgs[msg_idx[1]].format(**msg_params)
        ])
        ui.set_select(0)

    def __call__(self, radio=None, ui=None, short_press=[], long_press=[], msgs=None, msg_params=None, msg_idx=None, **kwargs):
        ui.draw_time()
        if 1 in short_press:
            return SeqSend(radio=radio, ui=ui, msgs=msgs, msg_params=msg_params, msg_idx=msg_idx, **kwargs)
        if 0 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[0] = (msg_idx[0] + 1) % len(msgs)
                self.show_msgs(ui, msgs, msg_params, msg_idx)
        if 2 in short_press:
            if msg_idx is not None and msgs is not None:
                msg_idx[1] = (msg_idx[1] + 1) % len(msgs)
                self.show_msgs(ui, msgs, msg_params, msg_idx)
        if 0 in long_press:
            print("RESET")
            msg_idx[0] = 0
            msg_idx[1] = 0
            msg_params['theircall'] = '______'
            msg_params['theirgrid'] = '______'
            msg_params['theirrssi'] = '___'
            msg_params['myrssi'] = '___'
            Seq.show_msgs(ui, msgs, msg_params, msg_idx)
        data = radio.receive(0.1)
        if data is not None:
            return SeqParse(data=data, ui=ui, radio=radio, msgs=msgs, msg_params=msg_params, msg_idx=msg_idx, **kwargs)
        return self


class SeqParse(State):
    RE_BCN = 'BCN'
    RE_CALL = '[A-Z0-9]+\d[A-Z0-9]*[A-Z]'
    RE_GRID = '[A-Z][A-Z][0-9][0-9][A-Z]*'
    RE_RSSI = '[+-][1-9][0-9]*'

    RE_BCN_MSG  = re.compile(f'^{RE_BCN}\s({RE_CALL})\s({RE_GRID})$')
    RE_CQ_MSG   = re.compile(f'^CQ\s({RE_CALL})\s({RE_GRID})$')
    RE_SEQ1_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\s({RE_GRID})$')
    RE_SEQ2_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\s({RE_RSSI})$')
    RE_SEQ3_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\sR({RE_RSSI})$')
    RE_SEQ4_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\sRRR$')
    RE_SEQ5_MSG = re.compile(f'^({RE_CALL})\s({RE_CALL})\s73$')

    def __init__(self, data=None, msgs=None, msg_idx=None, msg_params={}, ui=None, radio=None, **kwargs):
        super().__init__(**kwargs)
        try:
            data = data.decode().upper()
        except UnicodeError:
            ui.set_rx_error(True)
            print("Invalid: "+data)
	    # start matching message types. Only try and parse the expected type
        parsed = None
        if msg_idx[1] == 0:
            p = SeqParse.RE_CQ_MSG.match(data)
            if p is not None:
                msg_params['theircall'], msg_params['theirgrid'] = p.groups()
                print('CQ:', msg_params['theircall'], msg_params['theirgrid'])
                msg_idx[0] = 1
                msg_idx[1] = 2
                parsed = True
        elif msg_idx[1] == 1:
            p = SeqParse.RE_SEQ1_MSG.match(data)
            if p is not None:
                mycall, theircall, theirgrid = p.groups()
                print(msg_params['mycall'], mycall, theircall, theirgrid)
                if msg_params['mycall'] == mycall:
                    msg_params['theircall'], msg_params['theirgrid'] = theircall, theirgrid
                    print('RSP:', msg_params['theircall'], msg_params['theirgrid'])
                    msg_idx[0] = 2
                    msg_idx[1] = 3
                    parsed = True
        elif msg_idx[1] == 2:
            p = SeqParse.RE_SEQ2_MSG.match(data)
            if p is not None:
                mycall, theircall, myrssi = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    msg_params['myrssi'] = myrssi
                    print('RSSI:', msg_params['myrssi'])
                    parsed = True
                    msg_idx[0] = 3
                    msg_idx[1] = 4
        elif msg_idx[1] == 3:
            p = SeqParse.RE_SEQ3_MSG.match(data)
            if p is not None:
                mycall, theircall, myrssi = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    msg_params['myrssi'] = myrssi
                    print('RSSI:', msg_params['myrssi'])
                    parsed = True
                    msg_idx[0] = 4
                    msg_idx[1] = 5
        elif msg_idx[1] == 4:
            p = SeqParse.RE_SEQ4_MSG.match(data)
            if p is not None:
                mycall, theircall = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    # TODO: log
                    parsed = True
                    msg_idx[0] = 5
                    msg_idx[1] = 0
        elif msg_idx[1] == 5:
            p = SeqParse.RE_SEQ5_MSG.match(data)
            if p is not None:
                mycall, theircall = p.groups()
                if msg_params['mycall'] == mycall and msg_params['theircall'] == theircall:
                    # TODO: log
                    msg_params['theircall'] = '______'
                    msg_params['theirgrid'] = '______'
                    msg_params['theirrssi'] = '___'
                    msg_params['myrssi'] = '___'
                    parsed = True
                    msg_idx[0] = 0
                    msg_idx[1] = 0
	
        ui.set_rx_error(not parsed)
        if parsed:
            msg_params['theirrssi'] = radio.rssi
            Seq.show_msgs(ui, msgs, msg_params, msg_idx)

    def __call__(self, short_press=[], **kwargs):
        if 1 in short_press:
            return SeqSend(**kwargs)
        return Seq(**kwargs)


class SeqSend(State):
    def __init__(self, radio=None, ui=None, msgs=None, msg_idx=None, msg_params={}, config=None, **kwargs):
        super().__init__(**kwargs)
        if msgs is not None and msg_idx is not None:
            m = msgs[msg_idx[0]].format(**msg_params)
            ui.set_tx(True)
            print(f'SeqSend: {m}')
            for i in range(config.get('ping_length', 1)):
                radio.transmit(m)
                time.sleep(0.25)
            if msg_idx[0] == 0 and msg_idx[1] == 0:
                msg_idx[1] = 1

    def __call__(self, **kwargs):
        return Seq(**kwargs)


class Configure(State):
    def __init__(self, saved_state=None, **kwargs):
        super().__init__(**kwargs)
        self.__saved_state = saved_state


class StateMachine:
    def __init__(self, config):
        self.__state = InitialState()
        self.msg_idx=[0, 0]  # send, expected
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
            'theircall': '______',
            'theirgrid': '______',
            'theirrssi': '___',
            'myrssi': '___'
            }
        self.bkn_count = [0]
        self.config = config
    
    def __call__(self, **kwargs):
        kwargs.update(self.__dict__)
        long_press = kwargs.get('long_press', [])
        if 1 in long_press:  # special case, always jump to the configuration
            self.__state = Configure(saved_state=self.__state, **kwargs)
        self.__state = self.__state(**kwargs)
    
    def __str__(self):
        return f'StateMachine({self.__state.__class__.__name__})'