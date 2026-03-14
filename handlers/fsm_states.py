from aiogram.fsm.state import State, StatesGroup

class AuthStates(StatesGroup):
    waiting_for_password = State()
    waiting_for_phone = State()

class BookingStates(StatesGroup):
    waiting_for_start_time = State()
    waiting_for_end_time = State()
    
    def __init__(self):
        self.selected_car_id = None
        self.start_time = None

class AdminCarStates(StatesGroup):
    waiting_for_number_plate_delete = State()
    waiting_for_number_plate_edit = State()
    waiting_for_new_model = State()
    waiting_for_new_number = State()
    waiting_for_model = State()
    waiting_for_number = State() 