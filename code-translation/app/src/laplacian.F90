! laplacian.F90 -- five-point Laplacian of f on the interior, written with array sections.
subroutine laplacian(lap, f, nx, ny, dx, dy)
   use kinds, only: rk
   implicit none
   integer, intent(in) :: nx, ny
   real(rk), intent(inout) :: lap(0:nx+1, 0:ny+1)
   real(rk), intent(in) :: f(0:nx+1, 0:ny+1), dx, dy

   lap(1:nx, 1:ny) = (f(2:nx+1, 1:ny)-2.0_rk*f(1:nx, 1:ny)+f(0:nx-1, 1:ny))/dx**2 &
                     +(f(1:nx, 2:ny+1)-2.0_rk*f(1:nx, 1:ny)+f(1:nx, 0:ny-1))/dy**2
end subroutine laplacian
