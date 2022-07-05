import itertools
from gramps.gen.const import GRAMPS_LOCALE as glocale
_ = glocale.translation.gettext
from gramps.gen.filters.rules.person import MatchesFilter
from gramps.gen.filters.rules import Rule
from gramps.gui.editors.filtereditor import MyBoolean


def get_relatives(db, person):
    """
    Given a person handle, iterate all existing person handles of its
    relatives.

    adapted from IsRelatedWith.add_relative()
    """
    if person:
        for h in itertools.chain(
                # person as child
                person.get_parent_family_handle_list(),
                # person as parent
                person.get_family_handle_list(),
                ):
            family = db.get_family_from_handle(h)
            if family:
                # parents / spouse
                yield from (family.get_father_handle(),
                            family.get_mother_handle())
                # siblings / children
                for child_ref in family.get_child_ref_list():
                    yield child_ref.ref


class ExcludeSubtree(Rule):
    labels = [
        # see gramps.gui.editors.filtereditor.EditRule.__init__
        # must be (label, widget class) or special string as label
        _('ID:'),  # starting person
        (_('Include filter matches'), MyBoolean),
        _('Person filter name:'),  # TODO: also allow family filter
    ]
    name = _("People reachable from <Person>, stopping at <Filter> matches")
    category = _("Relationship filters")
    description = _("People reachable from <Person>, stopping at <Filter> matches")

    def prepare(self, db, user):
        self.reset()
        self.db = db

        if user:
            user.begin_progress(self.category,
                                _('Retrieving all sub-filter matches'),
                                db.get_number_of_people())
        try:
            start = db.get_person_from_gramps_id(self.list[0]).handle
            include_matched = bool(int(self.list[1]))
            self.filt = MatchesFilter(self.list[2:])
            self.filt.requestprepare(db, user)

            # walk the db using a queue
            search_list = [start]
            while search_list:
                if user:
                    user.step_progress()
                current_h = search_list.pop()
                current = db.get_person_from_handle(current_h)
                if current_h in self.matched_relatives:
                    continue  # already got them
                if self.filt.apply(db, current):
                    if include_matched:
                        self.matched_relatives.add(current_h)
                    continue  # stop at filter matches
                self.matched_relatives.add(current_h)
                # add their relatives to the search
                search_list.extend((h
                                    for h in get_relatives(db, current)
                                    if h))

        finally:
            if user:
                user.end_progress()

    def reset(self):
        self.matched_relatives = set()  # set of person handles

    def apply(self, db, person):
        return person.handle in self.matched_relatives
