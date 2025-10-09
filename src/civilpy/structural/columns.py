import math
from civilpy.structural.steel import HP

class Pier:
    """
    # //TODO - Used as a placeholder for the pile section class, will probably get updated and refined in a geotechnical module somewhere eventually.
    """
    def __init__(self, pier_id: int, pile_count: int):
        self.id = pier_id
        self.number_of_piles = pile_count
        self.piles = {i: None for i in range(1, pile_count + 1)}

    def __repr__(self):
        return f"<Pier #{self.id} with {self.number_of_piles} piles>"


class Pile:
    def __init__(self, pier: Pier, pile_number: int, section: str, insp_points: int,
                 length: float, youngs_modulus=29_000, yield_stress=44, poissons_ratio=0.3,
                 kf=1.277, kw=4.0,
                 K=1, web_plate_coeff=4, flange_plate_coeff=1.277):
        self.f_cre = None
        self.F_n = None
        self.f_crl = None
        self.eff_r_y = None
        self.eff_r_x = None
        self.eff_I_y = None
        self.eff_I_x = None
        self.section_loss = None
        self.eff_area = None
        self.lambda_c = None
        self.pier = pier
        self.pile_number = pile_number
        self.section = HP(section)  # //TODO - Probably should get switched to historical shapes
        self.insp_points = insp_points
        self.length = length
        self.youngs_modulus = youngs_modulus
        self.yield_stress = yield_stress
        self.poissons_ratio = poissons_ratio
        self.kf = kf
        self.kw = kw
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

    def run_all_calcs(self):
        self.get_section_averages()
        self.get_effective_area()
        self.get_strong_moment_of_inertia()
        self.get_weak_moment_of_inertia()
        self.get_radius_gyration()
        self.get_P_n()


    def get_section_averages(self):
        self.tl_avg = sum(self.top_left_tf.values()) / len(self.top_left_tf.values())
        self.tr_avg = sum(self.top_right_tf.values()) / len(self.top_right_tf.values())
        self.bl_avg = sum(self.bot_left_bf.values()) / len(self.bot_left_bf.values())
        self.br_avg = sum(self.bot_right_bf.values()) / len(self.bot_right_bf.values())
        self.tw_avg = sum(self.web_tw.values()) / len(self.web_tw.values())

    def get_effective_area(self):
        self.section.d2tf = self.section.depth.magnitude - 2 * self.section.flange_thickness.magnitude
        self.eff_area = sum([
            self.tl_avg * self.section.flange_width.magnitude / 2,
            self.tr_avg * self.section.flange_width.magnitude / 2,
            self.bl_avg * self.section.flange_width.magnitude / 2,
            self.br_avg * self.section.flange_width.magnitude / 2,
            self.tw_avg * self.section.d2tf
        ])

        self.section_loss = float((1 - self.eff_area / self.section.area.magnitude) * 100)

    def get_strong_moment_of_inertia(self):
        """
        Estimate the moment of inertia (Ix) of the pile cross-section using
        rectangular approximations and the parallel axis theorem.
        """
        # Ensure averages are calculated
        if None in (self.tl_avg, self.tr_avg, self.bl_avg, self.br_avg, self.tw_avg):
            raise ValueError("Section averages must be calculated before computing moment of inertia.")

        bf_half = self.section.flange_width.magnitude / 2  # Half flange width
        k2 = self.section.depth.magnitude - 2 * self.section.flange_thickness.magnitude

        def I_flange(tf):
            # Ix for a rectangle + parallel axis term
            return (1 / 12) * bf_half * tf ** 3 + bf_half * tf * ((k2 + tf) / 2) ** 2

        # Sum contributions from all four flanges
        I_flange_total = (
                I_flange(self.tl_avg) +
                I_flange(self.tr_avg) +
                I_flange(self.bl_avg) +
                I_flange(self.br_avg)
        )

        # Web contribution (centroid assumed at neutral axis)
        I_web = (1 / 12) * self.tw_avg * k2 ** 3

        self.eff_I_x = I_flange_total + I_web

        return I_flange_total + I_web

    def get_weak_moment_of_inertia(self):
        """
        Estimate the moment of inertia (Iy) of the pile cross-section using
        rectangular approximations and the parallel axis theorem.

        # //TODO - Can probably be combined with the above function
        """
        if None in (self.tl_avg, self.tr_avg, self.bl_avg, self.br_avg, self.tw_avg):
            raise ValueError("Section averages must be calculated before computing moment of inertia.")

        bf_half = self.section.flange_width.magnitude / 2  # Half flange width
        k2 = self.section.depth.magnitude - 2 * self.section.flange_thickness.magnitude  # Web height

        def I_flange_y(tf):
            # Iy for a vertical rectangle (tf wide, bf_half tall) + parallel axis
            return (1 / 12) * tf * bf_half ** 3 + tf * bf_half * (bf_half / 2) ** 2

        I_flange_total_y = (
                I_flange_y(self.tl_avg) +
                I_flange_y(self.tr_avg) +
                I_flange_y(self.bl_avg) +
                I_flange_y(self.br_avg)
        )

        # Web contribution (no offset from centroid)
        I_web_y = (1 / 12) * self.tw_avg ** 3 * k2

        self.eff_I_y = I_flange_total_y + I_web_y

        return I_flange_total_y + I_web_y

    def get_radius_gyration(self):
        self.eff_r_x = math.sqrt(self.eff_I_x / self.eff_area)
        self.eff_r_y = math.sqrt(self.eff_I_y / self.eff_area)

    def get_P_n(self):
        analysis_points = {0: self.tl_avg, 1: self.tr_avg, 2: self.bl_avg, 3: self.br_avg, 4: self.tw_avg}
        k_values = {0: self.kf, 1: self.kf, 2: self.kf, 3: self.kf, 4: self.kw}
        self.p_ns = {}

        for i in range(0, 5, 1):  # Perform the check for each element - 4 flanges/web
            thickness = analysis_points[i]
            k_value = k_values[i]

            if i == 4:
                depth = self.section.d2tf
            else:
                depth = self.section.flange_width.magnitude / 2

            self.f_crl = k_value * (math.pi ** 2 * self.youngs_modulus) / (12 * (1 - self.poissons_ratio ** 2) * (
                        (depth) / thickness) ** 2)
            self.f_cre = (math.pi ** 2 * self.youngs_modulus) / (
                        (self.K * self.length * 12 / min(self.eff_r_x, self.eff_r_y)) ** 2)
            self.lambda_c = math.sqrt(self.yield_stress / self.f_cre)

            if self.lambda_c <= 1.5:
                self.F_n = 0.658 ** self.lambda_c ** 2 * self.yield_stress
            else:
                self.F_n = (0.877 / self.lambda_c ** 2) * self.yield_stress

            self.lambda_var = math.sqrt(self.F_n / self.f_crl)

            if self.lambda_var <= 0.673:
                self.rho = 1
                self.b_e = depth
            else:
                self.rho = (1 - 0.22 / self.lambda_var) / self.lambda_var
                self.b_e = depth * self.rho

            self.A_e = self.b_e * thickness
            self.P_n = self.A_e * self.F_n

            self.p_ns[i] = self.P_n

            self.p_ns = self.p_ns
        return self.p_ns

    def __repr__(self):
        return f"<PileSection #{self.pile_number} with {self.insp_points} measurements>"