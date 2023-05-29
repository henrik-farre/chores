from datetime import date, datetime, timedelta




def get_weekdays_of_week(year, week_number):
    startdate = date.fromisocalendar(year, week_number, 1)

    dates = []
    for i in range(7):
        day = startdate + timedelta(days=i)
        dates.append(day)

    return dates


def get_week_number_from_date(date):
    week_number = date.isocalendar()[1]
    return week_number
