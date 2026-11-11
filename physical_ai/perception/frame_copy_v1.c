// Finite Host diagnostic copies. Each pre-faulted bytes object is published once.
// No SDK image/view is retained after copy. The caller exclusively owns the
// exporter during the call and passes its owner to pin the allocation lifetime.
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <time.h>

#define FRAME_BYTES (3840 * 2304 * 4)
#define MAX_CAPACITY 120
#define CAPSULE_NAME "stratadrive.frame_copy_v1"
typedef struct {
  PyObject *slots[MAX_CAPACITY];
  Py_ssize_t capacity, used, completed;
  uint64_t allocation_ns;
} CopyPool;

static uint64_t now_ns(void) {
  struct timespec t;
  clock_gettime(CLOCK_MONOTONIC, &t);
  return (uint64_t)t.tv_sec * 1000000000ULL + (uint64_t)t.tv_nsec;
}
static void free_pool(CopyPool *p) {
  if (!p) return;
  for (Py_ssize_t i = 0; i < p->capacity; ++i) Py_XDECREF(p->slots[i]);
  PyMem_Free(p);
}
static void destroy_pool(PyObject *capsule) {
  free_pool((CopyPool *)PyCapsule_GetPointer(capsule, CAPSULE_NAME));
}
static PyObject *create_pool(PyObject *self, PyObject *arg) {
  (void)self;
  if (!PyLong_CheckExact(arg)) {
    PyErr_SetString(PyExc_ValueError, "exact integer capacity required"); return NULL;
  }
  Py_ssize_t count = PyLong_AsSsize_t(arg);
  if (PyErr_Occurred()) return NULL;
  if (count < 1 || count > MAX_CAPACITY) {
    PyErr_SetString(PyExc_ValueError, "finite capacity1..120 required"); return NULL;
  }
  uint64_t start = now_ns();
  CopyPool *p = PyMem_Calloc(1, sizeof(*p));
  if (!p) return PyErr_NoMemory();
  p->capacity = count;
  for (Py_ssize_t i = 0; i < count; ++i) {
    p->slots[i] = PyBytes_FromStringAndSize(NULL, FRAME_BYTES);
    if (!p->slots[i]) { free_pool(p); return NULL; }
    char *dst = PyBytes_AS_STRING(p->slots[i]);
    // Still private: nobody can observe/hash these bytes before publication.
    Py_BEGIN_ALLOW_THREADS
    memset(dst, 0, FRAME_BYTES);
    Py_END_ALLOW_THREADS
  }
  p->allocation_ns = now_ns() - start;
  PyObject *result = PyCapsule_New(p, CAPSULE_NAME, destroy_pool);
  if (!result) free_pool(p);
  return result;
}
static PyObject *snapshot(PyObject *self, PyObject *args) {
  (void)self;
  PyObject *capsule, *source, *owner;
  if (!PyArg_ParseTuple(args, "OOO", &capsule, &source, &owner)) return NULL;
  CopyPool *p = PyCapsule_GetPointer(capsule, CAPSULE_NAME);
  if (!p) return NULL;
  if (!PyMemoryView_Check(source) || owner == Py_None) {
    PyErr_SetString(PyExc_ValueError, "read-only memoryview and pinned owner required"); return NULL;
  }
  Py_buffer *b = PyMemoryView_GET_BUFFER(source);
  if (!b->buf || !b->readonly || b->ndim != 1 || b->itemsize != 1 ||
      b->len != FRAME_BYTES || !PyBuffer_IsContiguous(b, 'C')) {
    PyErr_SetString(PyExc_ValueError, "exact contiguous read-only4K BGRA view required"); return NULL;
  }
  if (p->used == p->capacity) {
    PyErr_SetString(PyExc_BufferError, "finite frame-copy pool exhausted"); return NULL;
  }
  // Admission/reservation and publication occur under the GIL. Slots never recycle.
  PyObject *result = p->slots[p->used++];
  Py_INCREF(result); Py_INCREF(source); Py_INCREF(owner);
  char *dst = PyBytes_AS_STRING(result);
  const void *src = b->buf;
  Py_BEGIN_ALLOW_THREADS
  memcpy(dst, src, FRAME_BYTES);
  Py_END_ALLOW_THREADS
  ++p->completed;
  Py_DECREF(owner); Py_DECREF(source);
  return result;
}
static PyObject *stats(PyObject *self, PyObject *capsule) {
  (void)self;
  CopyPool *p = PyCapsule_GetPointer(capsule, CAPSULE_NAME);
  if (!p) return NULL;
  return Py_BuildValue("{s:n,s:n,s:n,s:K,s:K}",
    "capacity", p->capacity, "reserved", p->used, "completed", p->completed,
    "allocated_bytes", (unsigned long long)p->capacity * FRAME_BYTES,
    "allocation_ns", (unsigned long long)p->allocation_ns);
}
static PyMethodDef methods[] = {
  {"create", create_pool, METH_O, "Allocate and touch finite private image copies."},
  {"snapshot", snapshot, METH_VARARGS, "Copy while releasing GIL; publish immutable bytes once."},
  {"stats", stats, METH_O, "Read finite pool accounting."},
  {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = {
  PyModuleDef_HEAD_INIT, "_frame_copy_v1", NULL, -1, methods, NULL, NULL, NULL, NULL
};
PyMODINIT_FUNC PyInit__frame_copy_v1(void) { return PyModule_Create(&module); }
