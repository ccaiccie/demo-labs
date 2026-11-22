#include <stdio.h>
#include <stddef.h>

/* Only the GTK 3 and GObject ABI entry points used here. */
typedef struct _GtkWidget GtkWidget;
typedef struct _GClosure GClosure;
extern void gtk_init(int *, char ***);
extern GtkWidget *gtk_window_new(int);
extern void gtk_window_set_title(GtkWidget *, const char *);
extern void gtk_window_set_default_size(GtkWidget *, int, int);
extern GtkWidget *gtk_box_new(int, int);
extern void gtk_box_pack_start(GtkWidget *, GtkWidget *, int, int, unsigned);
extern void gtk_container_add(GtkWidget *, GtkWidget *);
extern void gtk_container_set_border_width(GtkWidget *, unsigned);
extern GtkWidget *gtk_label_new(const char *);
extern void gtk_label_set_xalign(GtkWidget *, float);
extern void gtk_label_set_text(GtkWidget *, const char *);
extern GtkWidget *gtk_entry_new(void);
extern void gtk_entry_set_placeholder_text(GtkWidget *, const char *);
extern void gtk_entry_set_max_length(GtkWidget *, int);
extern const char *gtk_entry_get_text(GtkWidget *);
extern GtkWidget *gtk_button_new_with_label(const char *);
extern void gtk_widget_show_all(GtkWidget *);
extern void gtk_widget_grab_focus(GtkWidget *);
extern void gtk_main(void);
extern void gtk_main_quit(void);
extern unsigned long g_signal_connect_data(void *, const char *, void (*)(void),
    void *, void (*)(void *, GClosure *), unsigned);

static const char *skip_spaces(const char *p) {
    while (*p == ' ' || *p == '\t') ++p;
    return p;
}
static int digit(char c) { return c >= '0' && c <= '9'; }

static int read_bill(const char *p, long long *cents) {
    long long whole = 0, fraction = 0;
    p = skip_spaces(p);
    if (!digit(*p)) return 0;
    while (digit(*p)) {
        whole = whole * 10 + (*p++ - '0');
        if (whole > 10000) return 0;
    }
    if (*p == '.') {
        ++p;
        if (!digit(*p)) return 0;
        fraction = (*p++ - '0') * 10;
        if (digit(*p)) fraction += *p++ - '0';
    }
    if (*skip_spaces(p)) return 0;
    *cents = whole * 100 + fraction;
    return *cents <= 1000000;
}

static int read_percent(const char *p, int *percent) {
    int n = 0;
    p = skip_spaces(p);
    if (!digit(*p)) return 0;
    while (digit(*p)) {
        n = n * 10 + (*p++ - '0');
        if (n > 100) return 0;
    }
    if (*skip_spaces(p)) return 0;
    *percent = n;
    return 1;
}

static long long get_tip(long long cents, int percent) {
    return (cents * percent + 50) / 100;
}

static void result_text(const char *bill, const char *percent, char *out, size_t size) {
    long long cents, tip, total;
    int rate;
    if (!read_bill(bill, &cents)) {
        snprintf(out, size, "Enter a bill from 0 to 10000.00 (up to 2 decimals).");
        return;
    }
    if (!read_percent(percent, &rate)) {
        snprintf(out, size, "Enter a whole tip percentage from 0 to 100.");
        return;
    }
    tip = get_tip(cents, rate);
    total = cents + tip;
    snprintf(out, size, "Tip: $%lld.%02lld    Total: $%lld.%02lld",
             tip / 100, tip % 100, total / 100, total % 100);
}

typedef struct { GtkWidget *bill, *percent, *result; } Widgets;

static void calculate(GtkWidget *sender, void *context) {
    (void)sender;
    Widgets *w = context;
    char out[128];
    result_text(gtk_entry_get_text(w->bill), gtk_entry_get_text(w->percent), out, sizeof out);
    gtk_label_set_text(w->result, out);
}
static void close_window(GtkWidget *sender, void *context) {
    (void)sender; (void)context;
    gtk_main_quit();
}
static GtkWidget *label(const char *text) {
    GtkWidget *w = gtk_label_new(text);
    gtk_label_set_xalign(w, 0.0f);
    return w;
}
static void pack(GtkWidget *box, GtkWidget *child) {
    gtk_box_pack_start(box, child, 0, 0, 0);
}
int main(int argc, char **argv) {
    gtk_init(&argc, &argv);
    GtkWidget *window = gtk_window_new(0);
    GtkWidget *box = gtk_box_new(1, 12);
    GtkWidget *button = gtk_button_new_with_label("Calculate");
    Widgets w = { gtk_entry_new(), gtk_entry_new(), label("Tip and total will appear here.") };
    gtk_window_set_title(window, "Tip Calculator");
    gtk_window_set_default_size(window, 460, 280);
    gtk_container_set_border_width(window, 24);
    gtk_container_add(window, box);
    pack(box, label("Tip Calculator"));
    pack(box, label("Bill amount (USD)"));
    gtk_entry_set_placeholder_text(w.bill, "e.g. 42.50");
    gtk_entry_set_max_length(w.bill, 32);
    pack(box, w.bill);
    pack(box, label("Tip percentage"));
    gtk_entry_set_placeholder_text(w.percent, "e.g. 18");
    gtk_entry_set_max_length(w.percent, 32);
    pack(box, w.percent);
    pack(box, button);
    pack(box, w.result);
    g_signal_connect_data(window, "destroy", (void (*)(void))close_window, NULL, NULL, 0);
    g_signal_connect_data(button, "clicked", (void (*)(void))calculate, &w, NULL, 0);
    g_signal_connect_data(w.bill, "activate", (void (*)(void))calculate, &w, NULL, 0);
    g_signal_connect_data(w.percent, "activate", (void (*)(void))calculate, &w, NULL, 0);
    gtk_widget_show_all(window);
    gtk_widget_grab_focus(w.bill);
    gtk_main();
    return 0;
}
