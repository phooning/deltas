# Each strategy is a dataclass of legs with entry/exit logic. Key structures to implement for the MVP: VerticalSpread, Calendar, IronCondor,
# Strangle, CoveredCall, LongCall. Each implements .legs(), .max_profit(), .max_loss(), .breakevens(), .required_margin().
