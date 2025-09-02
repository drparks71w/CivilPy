from civilpy.structural.steel import HP

class Pier:
    """
    # //TODO - Used as a placeholder for the pile section class, will probably get updated and refined in a geotechnical module somewhere eventually.
    """
    def __init__(self, pier_id: int, pile_count: int):
        self.id = pier_id
        self.number_of_piles = pile_count

    def __repr__(self):
        return f"<Pier #{self.id} with {self.number_of_piles} piles>"


class PileSection:
    def __init__(self, pier: Pier, pile_number: int, section: str, insp_points: int,
                 length: float, youngs_modulus=29_000, yield_stress=44, poissons_ratio=0.3,
                 K=1, web_plate_coeff=4, flange_plate_coeff=1.277):
        self.pier = pier
        self.pile_number = pile_number
        self.section = HP(section)  # //TODO - Probably should get switched to historical shapes
        self.insp_points = insp_points
        self.length = length
        self.youngs_modulus = youngs_modulus
        self.yield_stress = yield_stress
        self.poissons_ratio = poissons_ratio
        self.K = K
        self.web_plate_coeff = web_plate_coeff
        self.flange_plate_coeff = flange_plate_coeff

        # Each attribute is a dictionary: {measurement_number: thickness_value}
        self.top_left_tf = {i: None for i in range(1, insp_points + 1)}
        self.top_right_tf = {i: None for i in range(1, insp_points + 1)}
        self.bot_left_bf = {i: None for i in range(1, insp_points + 1)}
        self.bot_right_bf = {i: None for i in range(1, insp_points + 1)}
        self.web_tw = {i: None for i in range(1, insp_points + 1)}

        self.tl_avg = None
        self.tr_avg = None
        self.bl_avg = None
        self.br_avg = None
        self.tw_avg = None

    def get_section_averages(self):
        self.tl_avg = sum(self.top_left_tf.values()) / len(self.top_left_tf.values())
        self.tr_avg = sum(self.top_right_tf.values()) / len(self.top_right_tf.values())
        self.bl_avg = sum(self.bot_left_bf.values()) / len(self.bot_left_bf.values())
        self.br_avg = sum(self.bot_right_bf.values()) / len(self.bot_right_bf.values())
        self.tw_avg = sum(self.web_tw.values()) / len(self.web_tw.values())

    def __repr__(self):
        return f"<PileSection #{self.pile_number} with {self.insp_points} measurements>"
